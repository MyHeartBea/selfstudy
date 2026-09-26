"""AI 解析接口：题干解析、图片识别、知识点自动总结。"""

import json
import logging
import time
from typing import List

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.database import get_connection
from app.metrics import mask_secret
from app.responses import error, ok
from app.schemas import AiAnalyzeRequest, AiEnglishRequest, AiOcrRequest
from app.security import ai_rate_limit
from app.services import ai_service, local_ocr
from app.services.ai_service import AiNotConfigured, AiRequestError

logger = logging.getLogger("kaoyan.ai")

router = APIRouter(prefix="/api/ai", tags=["AI"])

# 科目提示词 → (科目关键词, 缺省二级科目名)
_SUBJECT_MAP = [
    ("数学", "数学", "高等数学"),
    ("英语", "英语", "阅读理解"),
    ("政治", "政治", "马克思主义基本原理"),
    ("408", 408, "计算机网络"),
    ("计算机", "计算机", "计算机网络"),
]


def _auto_subject_ids(conn, hint: str):
    """根据 subject_hint（如'数学'/'408'/'英语'）映射到 subject_id + 缺省二级科目 id。"""
    hint = str(hint or "").strip().lower()
    for kw, subj_kw, default_sub in _SUBJECT_MAP:
        if kw.lower() in hint:
            row = conn.execute(
                "SELECT id FROM subjects WHERE name LIKE ? LIMIT 1", (f"%{subj_kw}%",)
            ).fetchone()
            if row is None:
                return None, None
            subject_id = row["id"]
            sub = conn.execute(
                "SELECT id FROM sub_subjects WHERE subject_id=? AND name=? LIMIT 1",
                (subject_id, default_sub),
            ).fetchone()
            sub_id = sub["id"] if sub else None
            if sub_id is None:
                s = conn.execute(
                    "SELECT id FROM sub_subjects WHERE subject_id=? ORDER BY id LIMIT 1",
                    (subject_id,),
                ).fetchone()
                sub_id = s["id"] if s else None
            return subject_id, sub_id
    return None, None


AI_NOT_CONFIGURED_MESSAGE = (
    "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY、AI_BASE_URL、AI_MODEL"
)


def _vision_timeout_for(model: str, budget: float) -> int:
    """为首选视觉模型保留足够时间，同时受全局请求预算约束。"""
    is_primary = model.strip().lower() == settings.AI_VISION_DS_MODEL.strip().lower()
    limit = settings.AI_VISION_PRIMARY_TIMEOUT if is_primary else settings.AI_VISION_TIMEOUT
    return max(1, min(limit, int(budget)))


def _standard_tags() -> List[str]:
    conn = get_connection()
    try:
        # 按关联错题数量降序取高频标签（而非任意前 60 个），AI 更可能复用真实常用标签
        rows = conn.execute(
            "SELECT kb.tag_name, COUNT(mt.mistake_id) AS cnt "
            "FROM knowledge_base kb "
            "LEFT JOIN mistake_tag_map mt ON mt.tag = kb.tag_name "
            "GROUP BY kb.id ORDER BY cnt DESC, kb.tag_name COLLATE NOCASE LIMIT 60"
        ).fetchall()
        return [row["tag_name"] for row in rows]
    finally:
        conn.close()


def _apply_auto_subject(result: dict) -> None:
    """根据解析结果里的 subject_hint，自动填入 subject_id / sub_subject_id。"""
    conn = get_connection()
    try:
        sid, sub_id = _auto_subject_ids(conn, result.get("subject_hint"))
        if sid:
            result["subject_id"] = sid
            if sub_id:
                result["sub_subject_id"] = sub_id
    finally:
        conn.close()


def _ai_error_message(exc: Exception) -> str:
    if isinstance(exc, AiNotConfigured):
        return AI_NOT_CONFIGURED_MESSAGE
    # 上游 4xx 的响应体会原样进异常（`AI 服务返回 401: {...}`），个别网关把请求头
    # 回显在报错里。这些字符串会出现在前端 toast 上，一律先脱敏再返回。
    if isinstance(exc, AiRequestError):
        return mask_secret(str(exc))
    return mask_secret(f"AI 服务调用失败：{exc}")


def _degrade_note(failed_channels: List[str]) -> str:
    """降级提示后缀。

    通道按序回退时，前一个通道的异常会被后一个通道的成功掩盖，识别"照样出结果、
    只是又慢又抖" —— 以前只回一句"识别完成"，等于把通道故障藏起来，只能靠手感察觉。
    **措辞里的"已降级"是前端 CaptureView 判定要不要提醒的锚点**，改字要同步改那里。
    """
    if not failed_channels:
        return ""
    return f"（首选通道 {'、'.join(failed_channels)} 失败，已降级）"


@router.post("/analyze", dependencies=[Depends(ai_rate_limit)])
def analyze_text(body: AiAnalyzeRequest):
    """根据题干文本自动解析选项、答案、解析与知识点标签。"""
    try:
        result = ai_service.analyze_text(
            body.text,
            standard_tags=_standard_tags(),
            instruction=body.instruction,
        )
        conn = get_connection()
        try:
            sid, sub_id = _auto_subject_ids(conn, result.get("subject_hint"))
            if sid:
                result["subject_id"] = sid
                if sub_id:
                    result["sub_subject_id"] = sub_id
        finally:
            conn.close()
        return ok(result)
    except Exception as exc:
        return error(502, _ai_error_message(exc))


@router.post("/ocr", dependencies=[Depends(ai_rate_limit)])
def ocr_image(body: AiOcrRequest):
    """识别图片中的题目并生成结构化错题数据。

    配置了视觉模型时优先直接看图（最准）；否则本地 OCR 转文字再交给 AI 解析；
    最后退回默认模型的图片接口。
    """
    last_vision_error = ""
    last_local_error = ""
    vision_providers = _vision_providers()
    started = time.monotonic()
    # 标准标签只查一次，避免每个并发通道重复查询数据库
    standard_tags = _standard_tags()

    def remaining() -> float:
        return max(0.0, settings.AI_OCR_TOTAL_TIMEOUT - (time.monotonic() - started))

    def call_provider(vision_model, vision_base_url, vision_api_key):
        budget = remaining()
        if budget <= 2:
            raise RuntimeError("整体识别预算耗尽")
        return ai_service.ocr_image(
            body.image_base64,
            standard_tags=standard_tags,
            model=vision_model,
            base_url=vision_base_url,
            api_key=vision_api_key,
            # timeout 覆盖 ocr_image 全程（提字 + 文本分析），vision_timeout 只约束提字一步
            timeout=max(5, int(min(settings.AI_TIMEOUT, budget))),
            vision_timeout=_vision_timeout_for(vision_model, budget),
            instruction=body.instruction,
            reference_image_base64=body.reference_image_base64,
        )

    # Providers are ordered by reliability/cost preference. In particular,
    # DeepSeek Vision must be given the first opportunity to answer instead
    # of racing every configured provider and losing to a faster fallback.
    failed_channels: List[str] = []
    for provider in vision_providers:
        if remaining() <= 2:
            break
        try:
            parsed = call_provider(*provider)
            parsed["method"] = "vision"
            parsed["raw_text"] = ""
            parsed["vision_model"] = provider[0]
            _apply_auto_subject(parsed)
            return ok(parsed, f"视觉模型识别完成{_degrade_note(failed_channels)}")
        except Exception as exc:
            last_vision_error = str(exc)
            failed_channels.append(provider[0])
            logger.warning(
                "视觉通道 %s 失败，改用下一个兜底通道：%s",
                provider[0],
                mask_secret(last_vision_error),
            )
    try:
        if local_ocr.is_available():
            try:
                text = local_ocr.recognize_base64(body.image_base64)
                if text:
                    parsed = ai_service.analyze_text(
                        text,
                        standard_tags=standard_tags,
                        timeout=min(
                            settings.AI_TIMEOUT,
                            max(5, int(remaining())),
                        ),
                        instruction=body.instruction,
                    )
                    parsed["method"] = "local"
                    parsed["raw_text"] = text
                    reason = (
                        f"（视觉模型失败：{mask_secret(last_vision_error, 120)}）"
                        if last_vision_error
                        else ""
                    )
                    return ok(parsed, f"本地 OCR 识别完成{reason}")
            except Exception as exc:
                # 本地识别失败时退回多模态图片接口
                last_local_error = str(exc)
        budget = remaining()
        if budget <= 2:
            raise RuntimeError(
                f"图片识别超时，视觉模型失败：{mask_secret(last_vision_error) or '未配置可用模型'}"
            )
        parsed = ai_service.ocr_image(
            body.image_base64,
            standard_tags=standard_tags,
            timeout=max(5, int(min(settings.AI_TIMEOUT, budget))),
            instruction=body.instruction,
            reference_image_base64=body.reference_image_base64,
        )
        parsed["method"] = "vision"
        parsed["raw_text"] = ""
        parsed["vision_model"] = ""
        return ok(parsed)
    except Exception as exc:
        message = _ai_error_message(exc)
        if "image_url" in message:
            if last_vision_error:
                message = f"视觉模型识别失败：{mask_secret(last_vision_error)}"
            elif last_local_error:
                message = (
                    f"本地 OCR 失败：{mask_secret(last_local_error)}；"
                    "当前 AI 模型也不支持图片，请配置支持图片的模型"
                )
        return error(502, message)


@router.post("/english", dependencies=[Depends(ai_rate_limit)])
def english_analysis(body: AiEnglishRequest):
    """英语整篇精读：支持多张图片（原文段落 + 选项）或粘贴文本。

    自动检测是否为英语阅读：是则返回英语整篇结构（原文/翻译/句子拆解/短语/生词 + 题目解析）；
    否则返回通用错题结构（is_english=false），供前端降级到普通录入。
    带图时视觉通道按首选→后备逐个尝试（DeepSeek 失败自动换 GLM/Agnes），
    单次尝试的全程预算受 AI_OCR_TOTAL_TIMEOUT 约束。
    """
    started = time.monotonic()
    # 标准标签只查一次
    standard_tags = _standard_tags()

    def remaining() -> float:
        return max(0.0, settings.AI_OCR_TOTAL_TIMEOUT - (time.monotonic() - started))

    # 无图（纯文本）时单通道占位即可；带图时按配置顺序逐通道回退
    providers: List[tuple] = _vision_providers() if body.images else [(None, None, None)]
    parsed = None
    last_error: Exception | None = None
    failed_channels: List[str] = []
    for vision_model, vision_base_url, vision_api_key in providers:
        budget = remaining()
        if budget <= 2:
            break
        try:
            parsed = ai_service.analyze_english(
                body.images,
                text=body.text,
                standard_tags=standard_tags,
                instruction=body.instruction,
                timeout=max(5, int(min(settings.AI_TIMEOUT, budget))),
                vision_timeout=(
                    _vision_timeout_for(vision_model, budget) if vision_model else None
                ),
                model=vision_model,
                base_url=vision_base_url,
                api_key=vision_api_key,
            )
            break
        except AiNotConfigured:
            return error(400, AI_NOT_CONFIGURED_MESSAGE)
        except Exception as exc:
            last_error = exc
            failed_channels.append(str(vision_model or settings.AI_MODEL))
            logger.warning(
                "英语整篇通道 %s 失败，改用下一个兜底通道：%s",
                vision_model,
                mask_secret(str(exc)),
            )
    if parsed is None:
        message = (
            _ai_error_message(last_error)
            if last_error is not None
            else "图片识别超时：所有视觉通道均未在预算内完成"
        )
        return error(502, message)
    parsed["method"] = "vision" if body.images else "text"
    # 自动识别并填入 科目/二级科目（英语→阅读、数学→高数、408→计网等）
    if parsed.get("is_english") and not parsed.get("subject_hint"):
        parsed["subject_hint"] = "英语"
    conn = get_connection()
    try:
        sid, sub_id = _auto_subject_ids(conn, parsed.get("subject_hint"))
        if sid:
            parsed["subject_id"] = sid
            if sub_id:
                parsed["sub_subject_id"] = sub_id
    finally:
        conn.close()
    return ok(parsed, f"英语整篇解析完成{_degrade_note(failed_channels)}")


@router.post("/weekly-report", dependencies=[Depends(ai_rate_limit)])
def weekly_report(force: int = Query(0, ge=0, le=1)):
    """近 7 天错题的错因聚类周报（AI 生成，按天缓存；force=1 强制重新生成）。"""
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    cache_key = f"weekly_report_{today}"
    conn = get_connection()
    try:
        if not force:
            row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (cache_key,)).fetchone()
            if row and row["value"]:
                try:
                    cached = json.loads(row["value"])
                    cached["cached"] = True
                    return ok(cached)
                except (TypeError, ValueError):
                    pass
        rows = conn.execute(
            """
            SELECT m.id, m.question, m.knowledge_tags, r.note, r.user_answer,
                   s.name AS subject_name
            FROM review_records r
            JOIN mistakes m ON m.id = r.mistake_id
            LEFT JOIN subjects s ON s.id = m.subject_id
            WHERE r.result = 'wrong' AND r.reviewed_at >= datetime('now', '-7 days')
            ORDER BY r.reviewed_at DESC
            LIMIT 60
            """
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return ok({"empty": True, "message": "近 7 天没有答错记录，继续保持！"})
    items = [
        {
            "id": r["id"],
            "subject": r["subject_name"] or "",
            "question": (r["question"] or "")[:160],
            "tags": [t for t in (r["knowledge_tags"] or "").split(",") if t][:4],
            "note": (r["note"] or "")[:120],
            "user_answer": (r["user_answer"] or "")[:80],
        }
        for r in rows
    ]
    try:
        report = ai_service.analyze_weekly_report(items)
    except AiNotConfigured:
        return error(400, AI_NOT_CONFIGURED_MESSAGE)
    except Exception as exc:
        return error(502, _ai_error_message(exc))
    report["week_count"] = len(items)
    report["cached"] = False
    # 按天缓存进 app_meta，并清理历史日期的缓存
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
            (cache_key, json.dumps(report, ensure_ascii=False)),
        )
        for r in conn.execute(
            "SELECT key FROM app_meta WHERE key LIKE 'weekly_report_%' AND key != ?",
            (cache_key,),
        ).fetchall():
            if r["key"] < cache_key:
                conn.execute("DELETE FROM app_meta WHERE key = ?", (r["key"],))
        conn.commit()
    finally:
        conn.close()
    return ok(report)


# 点词查义缓存：词义不随时间变化，长期缓存省 AI 调用；按 TTL 过期 + 条目上限双清理
SENSE_CACHE_PREFIX = "sense_"
SENSE_CACHE_TTL_DAYS = 90
SENSE_CACHE_MAX_ENTRIES = 500


def _sense_cache_key(word: str) -> str:
    return SENSE_CACHE_PREFIX + (word or "").strip().lower()


def _read_sense_cache(conn, cache_key: str):
    """命中返回释义 dict（带 cached 标记），过期/损坏返回 None。"""
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (cache_key,)).fetchone()
    if not row or not row["value"]:
        return None
    try:
        cached = json.loads(row["value"])
    except (TypeError, ValueError):
        return None
    ts = float(cached.get("ts") or 0)
    data = cached.get("data")
    if not isinstance(data, dict) or not data.get("meanings"):
        return None
    if time.time() - ts > SENSE_CACHE_TTL_DAYS * 86400:
        return None
    payload = dict(data)
    payload["cached"] = True
    return payload


def _write_sense_cache(conn, cache_key: str, data: dict) -> None:
    """写缓存并清理：过期条目全删，超出上限按 ts 淘汰最旧。"""
    now = time.time()
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (cache_key, json.dumps({"ts": now, "data": data}, ensure_ascii=False)),
    )
    rows = conn.execute(
        "SELECT key, value FROM app_meta WHERE key LIKE ?",
        (SENSE_CACHE_PREFIX + "%",),
    ).fetchall()
    entries = []
    for row in rows:
        if row["key"] == cache_key:
            entries.append((cache_key, now))
            continue
        try:
            ts = float(json.loads(row["value"]).get("ts") or 0)
        except (TypeError, ValueError):
            ts = 0
        entries.append((row["key"], ts))
    stale = [key for key, ts in entries if now - ts > SENSE_CACHE_TTL_DAYS * 86400]
    keep = sorted((e for e in entries if e[0] not in set(stale)), key=lambda e: -e[1])
    stale.extend(key for key, _ in keep[SENSE_CACHE_MAX_ENTRIES:])
    for key in stale:
        conn.execute("DELETE FROM app_meta WHERE key = ?", (key,))
    conn.commit()


@router.get("/sense", dependencies=[Depends(ai_rate_limit)])
def word_sense(word: str = Query(..., min_length=1, max_length=120)):
    """点词/划词查义：用 AI 解释任意英语单词或短语（同词 90 天内直接走缓存）。"""
    cache_key = _sense_cache_key(word)
    conn = get_connection()
    try:
        cached = _read_sense_cache(conn, cache_key)
    finally:
        conn.close()
    if cached is not None:
        return ok(cached)
    try:
        result = ai_service.lookup_word(word)
    except AiNotConfigured:
        return error(400, AI_NOT_CONFIGURED_MESSAGE)
    except Exception as exc:
        return error(502, _ai_error_message(exc))
    # 查不到释义（空词/乱码）不缓存，下次重试可能就对了
    if result.get("meanings"):
        conn = get_connection()
        try:
            _write_sense_cache(conn, cache_key, result)
        finally:
            conn.close()
    return ok(result)


def _vision_extract_with_fallback(images: List[str], instruction: str) -> tuple:
    """视觉提文字 + 本地 OCR 兜底，多通道按顺序尝试（不并发）。

    返回 (文本, 错误信息)：文本非空即成功（此时错误信息通常为空）；
    文本为空时错误信息说明失败原因。整体受 AI_OCR_TOTAL_TIMEOUT 预算约束。

    **为什么改成顺序而不是并发**：原来把全部视觉通道同时提交，谁先返回用谁。
    但「成功一个」并不能撤销其它通道已发出的请求 —— HTTP 早已发出、图片早已上传，
    `f.cancel()` 对运行中的任务无效（只能取消未开始的）。而本机配了 6 个通道
    （DeepSeek + GLM/Agnes 各代），等于每次识图都把**同一份图片上传 6 次并付 6 次钱**，
    只留 1 份结果。顺序尝试只多花一点墙钟时间：首选命中即为 1 次调用。
    """
    last_error = ""
    providers = _vision_providers()
    started = time.monotonic()

    def remaining() -> float:
        return max(0.0, settings.AI_OCR_TOTAL_TIMEOUT - (time.monotonic() - started))

    raw_text = ""
    for vision_model, vision_base_url, vision_api_key in providers:
        budget = remaining()
        if budget <= 2:
            last_error = last_error or "整体识别预算耗尽"
            break
        try:
            text = ai_service.vision_extract_text_multi(
                images,
                timeout=_vision_timeout_for(vision_model, budget),
                instruction=instruction,
                model=vision_model,
                base_url=vision_base_url,
                api_key=vision_api_key,
            )
        except Exception as exc:
            last_error = mask_secret(str(exc))
            logger.warning("视觉提字通道 %s 失败，改用下一个兜底通道：%s", vision_model, last_error)
            continue
        if text and text.strip():
            raw_text = text.strip()
            break

    # 视觉失败降级本地 OCR
    if not raw_text and local_ocr.is_available():
        locals_text: List[str] = []
        for idx, img in enumerate(images):
            try:
                text = local_ocr.recognize_base64(img).strip()
            except Exception as exc:
                last_error = f"{last_error or '视觉失败'}; 本地 OCR: {exc}"
                continue
            if text:
                label = f"第{idx + 1}张" if len(images) > 1 else "识别结果"
                locals_text.append(f"【{label}】\n{text}")
        raw_text = "\n\n".join(locals_text).strip()

    return raw_text, last_error


def _vision_providers() -> List[tuple]:
    """构建视觉 provider 列表 (model, base_url, api_key)，按优先级顺序尝试。

    DeepSeek 视觉（走 AI_BASE_URL/AI_API_KEY，最准且支持图片缓存）为首选；
    其后是 GLM/Agnes 各代通道；全失败再降级本地 OCR。
    """
    providers = []
    # DeepSeek 多模态视觉模型（首选）：用文本模型的 base_url/api_key
    if settings.AI_VISION_DS_MODEL and settings.AI_API_KEY:
        providers.append(
            (settings.AI_VISION_DS_MODEL, settings.AI_BASE_URL or None, settings.AI_API_KEY or None)
        )
    for model in (
        settings.AI_VISION_MODEL,
        settings.AI_VISION_MODEL_FALLBACK,
    ):
        if model:
            providers.append(
                (model, settings.AI_VISION_BASE_URL or None, settings.AI_VISION_API_KEY or None)
            )
    for model in (
        settings.AI_VISION_2_MODEL,
        settings.AI_VISION_2_MODEL_FALLBACK,
    ):
        if model:
            providers.append(
                (model, settings.AI_VISION_2_BASE_URL or None, settings.AI_VISION_2_API_KEY or None)
            )
    if settings.AI_VISION_3_MODEL:
        providers.append(
            (
                settings.AI_VISION_3_MODEL,
                settings.AI_VISION_3_BASE_URL or None,
                settings.AI_VISION_3_API_KEY or None,
            )
        )
    return providers


@router.post("/knowledge-from-image", dependencies=[Depends(ai_rate_limit)])
def knowledge_from_image(body: AiOcrRequest):
    """粘贴图片 → 视觉识别提取文字 → AI 整理为知识点草稿（可带重点关注指令）。

    支持一次提交多张截图（body.images）：按粘贴顺序逐张提文字后合并，
    再统一整理成一个知识点草稿——避免"粘一张就分析一张"把同一知识点拆碎。
    """
    images = [str(img).strip() for img in body.images if str(img or "").strip()]
    if not images:
        images = [body.image_base64.strip()]

    raw_text, last_vision_error = _vision_extract_with_fallback(images, body.instruction)

    if not raw_text:
        return error(502, f"图片识别失败：{last_vision_error or '未能提取到文字'}")

    try:
        draft = ai_service.analyze_knowledge(
            raw_text,
            instruction=body.instruction,
        )
    except Exception as exc:
        return error(502, _ai_error_message(exc))

    draft["method"] = "vision" if not last_vision_error else "local"
    return ok(draft, "知识点草稿已生成，请核对后保存")
