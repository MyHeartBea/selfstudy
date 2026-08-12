"""本地 Windows OCR：先把截图转成文字，再交给 AI 文本解析。"""

import asyncio
import base64
import io
import re
from typing import List

try:
    from PIL import Image, ImageEnhance, ImageOps

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage.streams import (
        DataWriter,
        InMemoryRandomAccessStream,
    )

    WINSDK_AVAILABLE = True
except ImportError:
    WINSDK_AVAILABLE = False


def is_available() -> bool:
    """本地 OCR 是否可用。"""
    return WINSDK_AVAILABLE


def _score_text(text: str) -> float:
    """给 OCR 结果打分：中文优先，结果越长越优。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = len(re.findall(r"[A-Za-z0-9]", text))
    return cjk * 2 + latin * 0.5 + len(text) * 0.1


def _prepare_variants(data: bytes) -> List[bytes]:
    """生成多个预处理版本，交给 OCR 后选最优结果。"""
    if not PIL_AVAILABLE:
        return [data]
    image = Image.open(io.BytesIO(data)).convert("L")
    variants = [image, ImageOps.autocontrast(image)]

    for scale, contrast in ((2, 1.8), (3, 2.0)):
        enlarged = image.resize(
            (image.width * scale, image.height * scale),
            Image.LANCZOS,
        )
        enhanced = ImageEnhance.Contrast(ImageOps.autocontrast(enlarged)).enhance(contrast)
        variants.append(enhanced)

    outputs = []
    for variant in variants:
        buf = io.BytesIO()
        variant.save(buf, format="PNG")
        outputs.append(buf.getvalue())
    return outputs


def _pick_engine():
    """优先选择中文识别引擎，找不到时退回用户语言。"""
    languages = list(OcrEngine.available_recognizer_languages)
    if not languages:
        return OcrEngine.try_create_from_user_profile_languages()
    for language in languages:
        if str(language.language_tag).lower().startswith("zh"):
            return OcrEngine.try_create_from_language(language)
    return (
        OcrEngine.try_create_from_user_profile_languages()
        or OcrEngine.try_create_from_language(languages[0])
    )


async def _recognize(data: bytes) -> str:
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(data)
    await writer.store_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    engine = _pick_engine()
    if engine is None:
        raise RuntimeError("系统没有可用的 OCR 语言包，请安装中文识别语言")
    result = await engine.recognize_async(software_bitmap)
    return (result.text or "").strip()


def recognize_base64(image_base64: str) -> str:
    """把 base64 图片识别为文字。"""
    if not WINSDK_AVAILABLE:
        raise RuntimeError("本地 OCR 未安装，请先执行 pip install winsdk")
    raw = image_base64.strip()
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    data = base64.b64decode(raw)
    best_text = ""
    for variant in _prepare_variants(data):
        try:
            text = asyncio.run(_recognize(variant))
        except Exception:
            continue
        if _score_text(text) > _score_text(best_text):
            best_text = text
    return best_text
