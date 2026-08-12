"""统一 JSON 响应格式。"""

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any, message: str = "success") -> dict:
    return {"code": 200, "data": data, "message": message}


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "data": None, "message": message},
    )
