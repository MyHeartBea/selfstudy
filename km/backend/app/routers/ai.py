"""AI 解析接口：题干解析、图片识别、知识点自动总结。"""

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from fastapi import APIRouter
from typing import List

from app.config import settings
from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import AiAnalyzeRequest, AiOcrRequest
from app.services import ai_service, local_ocr
from app.services.ai_service import AiNotConfigured, AiRequestError

router = APIRouter(prefix="/api/ai", tags=["AI"])

AI_NOT_CONFIGURED_MESSAGE = (
    "未配置 AI 服务：请在 backend/.env 中填写 AI_API_KEY、AI_BASE_URL、AI_MODEL"
)

# 视觉模型并发池：常驻复用，避免每个 OCR 请求都新建/销毁线程池
_VISION_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="vision")


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
        return ok(
            ai_service.analyze_text(
                body.text,
                standard_tags=_standard_tags(),
                instruction=body.instruction,
            )
        )
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
    vision_providers = []
    for model in (
        settings.AI_VISION_MODEL,
        settings.AI_VISION_MODEL_FALLBACK,
    ):
        if model:
            vision_providers.append(
                (model, settings.AI_VISION_BASE_URL or None, settings.AI_VISION_API_KEY or None)
            )
    for model in (
        settings.AI_VISION_2_MODEL,
        settings.AI_VISION_2_MODEL_FALLBACK,
    ):
        if model:
            vision_providers.append(
                (model, settings.AI_VISION_2_BASE_URL or None, settings.AI_VISION_2_API_KEY or None)
            )
    if settings.AI_VISION_3_MODEL:
        vision_providers.append(
            (
                settings.AI_VISION_3_MODEL,
                settings.AI_VISION_3_BASE_URL or None,
                settings.AI_VISION_3_API_KEY or None,
            )
        )
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
            timeout=min(settings.AI_VISION_TIMEOUT, int(budget)),
            instruction=body.instruction,
            reference_image_base64=body.reference_image_base64,
        )

    if vision_providers:
        futures = {
            _VISION_EXECUTOR.submit(call_provider, model, base_url, api_key): (
                model,
                base_url,
                api_key,
            )
            for model, base_url, api_key in vision_providers
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
                provider = futures[future]
                try:
                    parsed = future.result()
                    parsed["method"] = "vision"
                    parsed["raw_text"] = ""
                    parsed["vision_model"] = provider[0]
                    return ok(parsed, "视觉模型识别完成")
                except Exception as exc:
                    last_vision_error = str(exc)
            if remaining() <= 2:
                break
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
            timeout=min(settings.AI_TIMEOUT, int(budget)),
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
