"""进程内轻量监控：请求计数、错误计数、慢请求 Top 与最近错误、**AI 通道统计**。

单用户单进程应用，不需要 Prometheus 这类重型方案；这里保留最小可用集合，
供 `/api/health` 暴露、便于回答"哪条接口慢 / 最近有没有 502 / 识图到底走的哪个通道"。

AI 通道统计是**为"静默降级"准备的**：视觉多通道轮询里，前一个通道抛错会被后一个
通道的成功盖掉（`routers/ai.py` 只把异常留在局部变量里），日志只有一行异常。
模型名过期、额度耗尽、key 失效这类问题，过去只能靠"识图变慢了"来察觉 —— 现在
`/api/health` 的 `metrics.ai.by_model` 直接写明每个通道调了几次、错了几次、最后一次错什么。
"""

import re
import threading
import time
from collections import deque
from urllib.parse import urlparse

from app.config import settings

_LOCK = threading.Lock()

# 每个端点的累计统计：{"GET /api/reviews/today": {"count","total_ms","max_ms","errors"}}
_endpoints: dict = {}
# 最近错误（路径、状态码、时间）
_recent_errors: deque = deque(maxlen=50)
# 最慢的若干次请求（用于定位慢端点）
_slowest: list = []
# AI 调用按模型归并：{"deepseek-flash": {"calls","errors","truncated",...}}
_ai: dict = {}
# 429（AI 端点限流）命中数：这类响应不算 5xx 错误，但用户会觉得"按钮没反应"
_throttled = 0
_started_at = time.time()


def _key(method: str, path: str) -> str:
    """把路径里的数字 id 归一化，避免每个 id 一条统计。"""
    parts = []
    for seg in path.split("/"):
        if seg.isdigit():
            parts.append("{id}")
        else:
            parts.append(seg)
    return f"{method} {'/'.join(parts)}"


# 上游 4xx 响应体会原样进错误信息（`AI 服务返回 401: {detail}`），个别网关会把
# 请求头回显在报错里。这些字符串会被 /api/health 公开读到，所以**存之前必须脱敏**。
_SECRET_RE = re.compile(
    r"""(
        sk-[A-Za-z0-9_\-]{6,}          # DeepSeek / 智谱常见的 key 前缀
        | (?i:api[_-]?key)["'\s:=]*[^"'\s,;}]{6,}   # 报错里回显的 api_key=xxx
        | (?i:bearer\s+)[A-Za-z0-9._\-]{6,}         # Authorization 头
    )""",
    re.VERBOSE,
)


def mask_secret(text: str, limit: int = 300) -> str:
    """把可能混进错误信息的密钥打码。只用于展示字段，不改原始异常。"""
    if not text:
        return ""
    return _SECRET_RE.sub("****", text)[:limit]


def _host_of(base_url: str) -> str:
    try:
        return urlparse(base_url or settings.AI_BASE_URL).netloc or "(默认端点)"
    except ValueError:
        return "(非法端点)"


def record_ai(
    model: str,
    base_url: str,
    duration_ms: float,
    *,
    ok: bool = True,
    truncated: bool = False,
    reasoning_tokens: int = 0,
    completion_tokens: int = 0,
    error: str = "",
) -> None:
    """记录一次 AI 调用（**失败也要记**，这是本函数的全部意义）。

    通道 = 模型名 + 端点。多通道轮询时前一个通道的异常会被后一个通道的成功盖掉，
    只有按通道各记一笔，`/api/health` 才能显示"识图首选通道其实在连续报错、
    每次都在偷偷走兜底"。耗时口径覆盖 `_chat` 内部的重试与预算翻倍，
    即"这个通道交付一次结果要多久"。
    """
    key = f"{model or '(默认模型)'} @ {_host_of(base_url)}"
    with _LOCK:
        item = _ai.setdefault(
            key,
            {
                "calls": 0,
                "errors": 0,
                "truncated": 0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "reasoning_tokens": 0,
                "completion_tokens": 0,
                "last_error": "",
                "last_error_at": "",
                "last_at": "",
            },
        )
        item["calls"] += 1
        item["total_ms"] += duration_ms
        item["max_ms"] = max(item["max_ms"], duration_ms)
        item["reasoning_tokens"] += int(reasoning_tokens or 0)
        item["completion_tokens"] += int(completion_tokens or 0)
        item["last_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if truncated:
            item["truncated"] += 1
        if not ok:
            item["errors"] += 1
            item["last_error"] = mask_secret(error)
            item["last_error_at"] = time.strftime("%Y-%m-%d %H:%M:%S")


def record(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """记录一次请求。"""
    global _throttled
    key = _key(method, path)
    is_error = status_code >= 500
    is_slow = duration_ms >= settings.SLOW_REQUEST_MS
    with _LOCK:
        if status_code == 429:
            # 限流走的是 AI_RATE_LIMIT（AI 端点每分钟）——不是 5xx、不进 recent_errors，
            # 但用户看到的就是"点了按钮没反应"，所以要单独计数
            _throttled += 1
        item = _endpoints.setdefault(
            key,
            {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "errors": 0, "slow": 0},
        )
        item["count"] += 1
        item["total_ms"] += duration_ms
        item["max_ms"] = max(item["max_ms"], duration_ms)
        if is_error:
            item["errors"] += 1
            _recent_errors.append(
                {
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "ms": round(duration_ms, 1),
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        if is_slow:
            item["slow"] += 1
            _slowest.append(
                {
                    "method": method,
                    "path": path,
                    "ms": round(duration_ms, 1),
                    "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            _slowest.sort(key=lambda x: x["ms"], reverse=True)
            del _slowest[20:]


def snapshot(top: int = 5) -> dict:
    """返回监控摘要（供 /api/health）。"""
    with _LOCK:
        total = sum(v["count"] for v in _endpoints.values())
        errors = sum(v["errors"] for v in _endpoints.values())
        slow = sum(v["slow"] for v in _endpoints.values())
        calls = sum(v["calls"] for v in _ai.values())
        ai_errors = sum(v["errors"] for v in _ai.values())
        truncated = sum(v["truncated"] for v in _ai.values())
        by_channel = sorted(
            (
                {
                    "channel": k,
                    "calls": v["calls"],
                    "errors": v["errors"],
                    "truncated": v["truncated"],
                    "avg_ms": round(v["total_ms"] / v["calls"], 1) if v["calls"] else 0,
                    "max_ms": round(v["max_ms"], 1),
                    # 推理 token 均值：deepseek-flash 是推理模型，这个数暴涨说明
                    # max_tokens 预算正被 reasoning 吃掉（见 ai_service 的余量注释）
                    "reasoning_avg": round(v["reasoning_tokens"] / v["calls"]) if v["calls"] else 0,
                    "last_error": v["last_error"],
                    "last_error_at": v["last_error_at"],
                    "last_at": v["last_at"],
                }
                for k, v in _ai.items()
            ),
            key=lambda x: (-x["calls"], -x["errors"]),
        )
        ranked = sorted(
            (
                {
                    "endpoint": k,
                    "count": v["count"],
                    "avg_ms": round(v["total_ms"] / v["count"], 1) if v["count"] else 0,
                    "max_ms": round(v["max_ms"], 1),
                    "errors": v["errors"],
                }
                for k, v in _endpoints.items()
            ),
            key=lambda x: x["avg_ms"],
            reverse=True,
        )[:top]
        return {
            "uptime_seconds": int(time.time() - _started_at),
            "requests_total": total,
            "errors_total": errors,
            "slow_total": slow,
            "throttled_total": _throttled,
            "slow_threshold_ms": settings.SLOW_REQUEST_MS,
            "slowest_endpoints": ranked,
            "recent_errors": list(_recent_errors)[-5:],
            "slowest_requests": _slowest[:5],
            "ai": {
                "calls_total": calls,
                "errors_total": ai_errors,
                "truncated_total": truncated,
                # 按调用次数降序：主力通道排在前面，出错的那个 last_error 一眼可见
                "by_model": by_channel,
            },
        }


def reset() -> None:
    """仅测试使用。"""
    global _throttled
    with _LOCK:
        _endpoints.clear()
        _recent_errors.clear()
        _slowest.clear()
        _ai.clear()
        _throttled = 0
