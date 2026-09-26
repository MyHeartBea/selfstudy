"""考研英语作文批改接口：/api/essays。"""

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.database import get_connection
from app.metrics import mask_secret
from app.responses import error, ok
from app.schemas import AiEssayRequest
from app.security import ai_rate_limit
from app.services import ai_essay, local_ocr, search_service
from app.services.ai_essay import ESSAY_KINDS
from app.services.ai_service import AiNotConfigured

from app.routers.ai import _ai_error_message, _vision_providers, _vision_timeout_for

logger = logging.getLogger("kaoyan.essay")
router = APIRouter(prefix="/api/essays", tags=["作文"])


def _clean_images(body: AiEssayRequest) -> List[str]:
    images = [str(img).strip() for img in body.images if str(img or "").strip()]
    if not images and body.image_base64.strip():
        images = [body.image_base64.strip()]
    return images


def _transcribe(images: List[str], started: float) -> tuple:
    """手写稿 → 转录文本：视觉通道按序回退，全败降级本地 OCR。

    返回 (text, error_message)。遵循「先提文字再分析」，禁止单次超大视觉生成。
    """

    def remaining() -> float:
        return max(0.0, settings.AI_OCR_TOTAL_TIMEOUT - (time.monotonic() - started))

    last_error = ""
    for vision_model, vision_base_url, vision_api_key in _vision_providers():
        if remaining() <= 2:
            break
        try:
            text = ai_essay.extract_essay_text(
                images,
                timeout=_vision_timeout_for(vision_model, remaining()),
                model=vision_model,
                base_url=vision_base_url,
                api_key=vision_api_key,
            )
        except Exception as exc:
            # 与 /api/ai/ocr 同理：通道按序回退，前一个失败会被后一个成功掩盖。
            # 降级必须留下 WARN 痕迹（并按通道进 metrics.ai），否则只能靠"变慢了"察觉。
            last_error = mask_secret(str(exc))
            logger.warning("作文转录通道 %s 失败，改用下一个兜底通道：%s", vision_model, last_error)
            continue
        if text:
            return text, ""
    if local_ocr.is_available():
        parts = []
        for img in images:
            try:
                got = local_ocr.recognize_base64(img)
            except Exception as exc:
                last_error = last_error or mask_secret(str(exc))
                continue
            if got:
                parts.append(got)
        text = "\n\n".join(parts)
        if text:
            return text, ""
    return "", last_error or "视觉通道与本地 OCR 均未能提取文字"


@router.post("/grade", dependencies=[Depends(ai_rate_limit)])
def grade_essay(body: AiEssayRequest):
    """批改一篇英语作文：图片先原样转录，再按考研评分档批改并存档。"""
    started = time.monotonic()
    kind = body.kind if body.kind in ESSAY_KINDS else "e2_long"
    essay_text = body.text.strip()
    transcript_warning = ""
    if not essay_text:
        images = _clean_images(body)
        if not images:
            return error(400, "请提供作文图片或直接粘贴作文文本")
        try:
            essay_text, transcript_warning = _transcribe(images, started)
        except Exception as exc:
            return error(502, _ai_error_message(exc))
        if not essay_text:
            return error(502, f"作文图片识别失败：{transcript_warning}")
    try:
        result = ai_essay.grade_essay(
            essay_text,
            kind,
            prompt_text=body.prompt_text,
            instruction=body.instruction,
            timeout=max(5, int(settings.AI_TIMEOUT)),
        )
    except AiNotConfigured:
        return error(400, "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY 等")
    except Exception as exc:
        return error(502, _ai_error_message(exc))

    record_id = None
    persist_error = ""
    if body.persist:
        # 存档失败绝不能把已经花掉的批改结果一起带走：捕获后照样 200 返回，
        # 用 persisted/record_id 告诉前端"这份结果没进档案页"，由用户决定重试。
        try:
            conn = get_connection()
            try:
                cur = conn.execute(
                    "INSERT INTO essay_records (kind, prompt_text, essay_text, score, max_score,"
                    " result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                    (
                        kind,
                        body.prompt_text.strip(),
                        essay_text,
                        result["score"],
                        result["max_score"],
                        ai_essay.essay_result_json(result),
                    ),
                )
                record_id = cur.lastrowid
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.exception("作文批改结果存档失败")
            persist_error = str(exc) or exc.__class__.__name__
    result["record_id"] = record_id
    if body.persist:
        result["persisted"] = record_id is not None
    if persist_error:
        result["persist_error"] = persist_error
    if transcript_warning:
        result["transcript_warning"] = transcript_warning
    return ok(result, "批改完成" if not persist_error else "批改完成（存档失败，结果未进档案页）")


def _row_brief(row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "kind_name": (ESSAY_KINDS.get(row["kind"]) or {}).get("name", ""),
        "prompt_text": row["prompt_text"],
        "score": row["score"],
        "max_score": row["max_score"],
        "created_at": row["created_at"],
        "excerpt": (row["essay_text"] or "")[:80],
    }


@router.get("")
def list_essays(
    kind: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=80),
    page: int = Query(1, ge=1),
    # 分页参数名全站统一为 page_size（mistakes / knowledge / vocab 都是它）。
    # 这里原先叫 per_page，是全站唯一的例外 —— 前端 EssayView 要同步改。
    page_size: int = Query(15, ge=1, le=100),
):
    """作文批改历史（按时间倒序，服务端分页）。"""
    conn = get_connection()
    try:
        where = ""
        params: list = []
        if kind and kind in ESSAY_KINDS:
            where = "WHERE kind = ?"
            params.append(kind)
        if search and search.strip():
            # 转义 LIKE 通配符：搜 "50%" 不该命中所有含 5 的批改记录
            like = search_service.like_pattern(search.strip())
            clause = "(prompt_text LIKE ? ESCAPE '\\' OR essay_text LIKE ? ESCAPE '\\')"
            where = f"{where} AND {clause}" if where else f"WHERE {clause}"
            params.extend([like, like])
        total = conn.execute(f"SELECT COUNT(*) AS c FROM essay_records {where}", params).fetchone()[
            "c"
        ]
        rows = conn.execute(
            f"SELECT * FROM essay_records {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
        # page/page_size 之前漏在信封外（全站其余分页端点都带）——补齐，属加字段不减字段
        return ok(
            {
                "items": [_row_brief(r) for r in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    finally:
        conn.close()


@router.get("/trend")
def essays_trend():
    """全部批改记录的得分率时间序列（时间正序）：作文进步曲线用。

    列表页的分页趋势条只反映当前页；这里一次给全量（单用户量级百条以内，
    全量返回比前端拼分页简单可靠）。**必须声明在 /{essay_id} 之前**，
    否则 "trend" 会先撞进 int 路径参数返回 422。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kind, score, max_score, created_at FROM essay_records ORDER BY id ASC"
        ).fetchall()
        return ok(
            [
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "score": r["score"],
                    "max_score": r["max_score"],
                    "created_at": r["created_at"],
                    "pct": round((r["score"] or 0) / (r["max_score"] or 1) * 100),
                }
                for r in rows
            ]
        )
    finally:
        conn.close()


@router.get("/{essay_id}")
def get_essay(essay_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM essay_records WHERE id = ?", (essay_id,)).fetchone()
        if row is None:
            return error(404, "作文记录不存在")
        try:
            result = json.loads(row["result_json"] or "{}")
        except (TypeError, ValueError):
            result = {}
        brief = _row_brief(row)
        brief["essay_text"] = row["essay_text"]
        brief["result"] = result
        return ok(brief)
    finally:
        conn.close()


@router.delete("/{essay_id}")
def delete_essay(essay_id: int):
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM essay_records WHERE id = ?", (essay_id,))
        conn.commit()
        if cur.rowcount == 0:
            return error(404, "作文记录不存在")
        return ok({"deleted": essay_id})
    finally:
        conn.close()
