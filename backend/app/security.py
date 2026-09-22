"""轻量安全层：可选 API Token 鉴权 + AI 端点内存滑动窗口限流。

单机定位下默认零配置（不设 API_TOKEN 即放行）；一旦设置，
所有 /api 请求必须携带 token，防止误对外暴露时被刷 AI 额度或导出数据。
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app.config import settings


TOKEN_COOKIE = "km_token"


def _provided_token(request: Request, x_api_token: str | None, authorization: str | None) -> str:
    """按优先级取请求携带的 token。

    `<img>` 标签发不了自定义头，所以除两种 header 外还接受 cookie（前端 boot 时写入，
    覆盖 /images 静态文件与缩略图）与 query 参数（手工调试/命令行用）。
    """
    provided = (x_api_token or request.headers.get("x-api-token") or "").strip()
    if not provided:
        authorization = authorization or request.headers.get("authorization")
        if authorization:
            # 支持 Authorization: Bearer <token> 形式
            scheme, _, value = authorization.partition(" ")
            if scheme.lower() == "bearer":
                provided = value.strip()
    if not provided:
        provided = (request.query_params.get("api_token") or "").strip()
    if not provided:
        provided = (request.cookies.get(TOKEN_COOKIE) or "").strip()
    return provided


def token_configured() -> bool:
    return bool((settings.API_TOKEN or "").strip())


def token_ok(
    request: Request,
    x_api_token: str | None = None,
    authorization: str | None = None,
) -> bool:
    """未配置 token 时放行（单机零配置）；配置了则要求请求携带一致 token。"""
    if not token_configured():
        return True
    return (
        _provided_token(request, x_api_token, authorization) == (settings.API_TOKEN or "").strip()
    )


def verify_api_token(
    request: Request,
    x_api_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """校验 API Token（可选）。未配置 token 时放行，保持单机零配置可用。"""
    if not token_ok(request, x_api_token, authorization):
        raise HTTPException(status_code=401, detail="未授权：API Token 无效或缺失")


class _SlidingWindowLimiter:
    """按 (endpoint, client_ip) 维度的滑动窗口限流，线程安全。"""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


# AI 端点限流：默认每分钟 30 次（单机个人使用足够，防脚本刷额度）
_ai_limiter = _SlidingWindowLimiter(settings.AI_RATE_LIMIT)


def ai_rate_limit(request: Request) -> None:
    """AI 端点限流：超限返回 429。"""
    client = request.client.host if request.client else "unknown"
    if not _ai_limiter.allow((request.url.path, client)):
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试（AI 端点限流）",
        )
