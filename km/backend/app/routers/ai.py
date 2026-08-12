"""AI 解析接口：题干解析、图片识别、知识点自动总结。"""

from fastapi import APIRouter
from typing import List

from app.config import settings
from app.database import get_connection
from app.responses import error, ok
from app.schemas import AiAnalyzeRequest, AiOcrRequest
from app.services import ai_service, local_ocr
from app.services.ai_service import AiNotConfigured, AiRequestError

router = APIRouter(prefix="/api/ai", tags=["AI"])

AI_NOT_CONFIGURED_MESSAGE = (
    "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY、AI_BASE_URL、AI_MODEL"
)


def _standard_tags() -> List[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tag_name FROM knowledge_base "
            "ORDER BY tag_name COLLATE NOCASE LIMIT 60"
        ).fetchall()
        return [row["tag_name"] for row in rows]
    finally:
        conn.close()


def _ai_error_message(exc: Exception) -> str:
    if isinstance(exc, AiNotConfigured):
        return AI_NOT_CONFIGURED_MESSAGE
    if isinstance(exc, AiRequestError):
        return str(exc)
    return f"AI 服务调用失败：{exc}"


@router.post("/analyze")
def analyze_text(body: AiAnalyzeRequest):
    """根据题干文本自动解析选项、答案、解析与知识点标签。"""
    try:
        return ok(ai_service.analyze_text(body.text, standard_tags=_standard_tags()))
    except Exception as exc:
        return error(502, _ai_error_message(exc))


@router.post("/ocr")
def ocr_image(body: AiOcrRequest):
    """识别图片中的题目并生成结构化错题数据。

    配置了视觉模型时优先直接看图（最准）；否则本地 OCR 转文字再交给 AI 解析；
    最后退回默认模型的图片接口。
    """
    last_vision_error = ""
    last_local_error = ""
    vision_models = [
        model
        for model in (
            settings.AI_VISION_MODEL,
            settings.AI_VISION_MODEL_FALLBACK,
        )
        if model
    ]
    for vision_model in vision_models:
        try:
            parsed = ai_service.ocr_image(
                body.image_base64,
                standard_tags=_standard_tags(),
                model=vision_model,
            )
            parsed["method"] = "vision"
            parsed["raw_text"] = ""
            parsed["vision_model"] = vision_model
            return ok(
                parsed,
                "视觉模型识别完成",
            )
        except Exception as exc:
            last_vision_error = str(exc)
    try:
        if local_ocr.is_available():
            try:
                text = local_ocr.recognize_base64(body.image_base64)
                if text:
                    parsed = ai_service.analyze_text(
                        text,
                        standard_tags=_standard_tags(),
                    )
                    parsed["method"] = "local"
                    parsed["raw_text"] = text
                    return ok(parsed, "本地 OCR 识别完成")
            except Exception as exc:
                # 本地识别失败时退回多模态图片接口
                last_local_error = str(exc)
        parsed = ai_service.ocr_image(
            body.image_base64,
            standard_tags=_standard_tags(),
        )
        parsed["method"] = "vision"
        parsed["raw_text"] = ""
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
