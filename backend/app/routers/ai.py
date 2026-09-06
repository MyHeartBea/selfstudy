"""AI 解析接口：题干解析、图片识别、知识点自动总结。"""

import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from fastapi import APIRouter, Depends, Query
from typing import List

from app.config import settings
from app.database import get_connection
from app.responses import error, ok
from app.schemas import AiAnalyzeRequest, AiEnglishRequest, AiOcrRequest
from app.security import ai_rate_limit
from app.services import ai_service, local_ocr
from app.services.ai_service import AiNotConfigured, AiRequestError

router = APIRouter(prefix="/api/ai", tags=["AI"])

# 视觉模型并发执行器：knowledge-from-image 会并行尝试多个视觉通道
_VISION_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="km-vision")

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
    limit = (
        settings.AI_VISION_PRIMARY_TIMEOUT
        if is_primary
        else settings.AI_VISION_TIMEOUT
    )
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
    if isinstance(exc, AiRequestError):
        return str(exc)
    return f"AI 服务调用失败：{exc}"


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
    for provider in vision_providers:
        if remaining() <= 2:
            break
        try:
            parsed = call_provider(*provider)
            parsed["method"] = "vision"
            parsed["raw_text"] = ""
            parsed["vision_model"] = provider[0]
            _apply_auto_subject(parsed)
            return ok(parsed, "视觉模型识别完成")
        except Exception as exc:
            last_vision_error = str(exc)
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
                        f"（视觉模型失败：{last_vision_error[:120]}）"
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
                f"图片识别超时，视觉模型失败：{last_vision_error or '未配置可用模型'}"
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
                message = f"视觉模型识别失败：{last_vision_error}"
            elif last_local_error:
                message = (
                    f"本地 OCR 失败：{last_local_error}；"
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
                    _vision_timeout_for(vision_model, budget)
                    if vision_model
                    else None
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
    return ok(parsed, "英语整篇解析完成")


@router.get("/sense")
def word_sense(word: str = Query(..., min_length=1, max_length=60)):
    """点词查义：用 AI 解释任意英语单词，返回多词性释义。"""
    try:
        return ok(ai_service.lookup_word(word))
    except AiNotConfigured:
        return error(400, AI_NOT_CONFIGURED_MESSAGE)
    except AiRequestError as exc:
        return error(502, str(exc))
    except Exception as exc:
        return error(502, f"AI 服务调用失败：{exc}")


def _vision_providers() -> List[tuple]:
    """构建视觉 provider 列表 (model, base_url, api_key)。

    DeepSeek-V4-Flash-Vision-Exp 作为首选（走 AI_BASE_URL/AI_API_KEY，便宜且精度高），
    其后是 GLM/Agnes 三通道；全失败再降级本地 OCR。
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
    """粘贴图片 → 视觉识别提取文字 → AI 整理为知识点草稿（可带重点关注指令）。"""
    last_vision_error = ""
    providers = _vision_providers()
    started = time.monotonic()

    def remaining() -> float:
        return max(0.0, settings.AI_OCR_TOTAL_TIMEOUT - (time.monotonic() - started))

    def call_provider(vision_model, vision_base_url, vision_api_key):
        budget = remaining()
        if budget <= 2:
            raise RuntimeError("整体识别预算耗尽")
        return ai_service.vision_extract_text(
            body.image_base64,
            timeout=_vision_timeout_for(vision_model, budget),
            instruction=body.instruction,
            model=vision_model,
            base_url=vision_base_url,
            api_key=vision_api_key,
        )

    raw_text = ""
    if providers:
        futures = {
            _VISION_EXECUTOR.submit(call_provider, model, base_url, api_key): (
                model,
                base_url,
                api_key,
            )
            for model, base_url, api_key in providers
        }
        pending = set(futures)
        while pending:
            wait_timeout = max(0.1, min(2.0, remaining()))
            done, _ = wait(
                pending,
                timeout=wait_timeout,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                if remaining() <= 2:
                    break
                continue
            for future in done:
                pending.discard(future)
                try:
                    text = future.result()
                    if text and text.strip():
                        raw_text = text.strip()
                        break
                except Exception as exc:
                    last_vision_error = str(exc)
            if raw_text:
                for f in pending:
                    f.cancel()
                break

    # 视觉失败降级本地 OCR
    if not raw_text and local_ocr.is_available():
        try:
            raw_text = local_ocr.recognize_base64(body.image_base64).strip()
        except Exception as exc:
            last_vision_error = f"{last_vision_error or '视觉失败'}; 本地 OCR: {exc}"

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
