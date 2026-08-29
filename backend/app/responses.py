"""统一 JSON 响应格式。"""

import logging
from typing import Any

from fastapi.responses import JSONResponse

logger = logging.getLogger("kaoyan")


def ok(data: Any, message: str = "success") -> dict:
    return {"code": 200, "data": data, "message": message}


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "data": None, "message": message},
    )


def server_error(exc: Exception, context: str = "接口异常") -> JSONResponse:
    """记录完整异常堆栈，返回不泄露内部细节的 500 响应。"""
    logger.exception("%s：%s", context, exc)
    return error(500, "服务器内部错误，请稍后重试")
