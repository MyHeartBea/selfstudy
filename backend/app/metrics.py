"""进程内轻量监控：请求计数、错误计数、慢请求 Top 与最近错误。

单用户单进程应用，不需要 Prometheus 这类重型方案；这里保留最小可用集合，
供 `/api/health` 暴露、便于回答"哪条接口慢 / 最近有没有 502"。
"""

import threading
import time
from collections import Counter, deque
from typing import Optional

from app.config import settings

_LOCK = threading.Lock()

# 每个端点的累计统计：{"GET /api/reviews/today": {"count","total_ms","max_ms","errors"}}
_endpoints: dict = {}
# 最近错误（路径、状态码、时间）
_recent_errors: deque = deque(maxlen=50)
# 最慢的若干次请求（用于定位慢端点）
_slowest: list = []
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


def record(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """记录一次请求。"""
    key = _key(method, path)
    is_error = status_code >= 500
    is_slow = duration_ms >= settings.SLOW_REQUEST_MS
    with _LOCK:
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
            "slow_threshold_ms": settings.SLOW_REQUEST_MS,
            "slowest_endpoints": ranked,
            "recent_errors": list(_recent_errors)[-5:],
            "slowest_requests": _slowest[:5],
        }


def reset() -> None:
    """仅测试使用。"""
    with _LOCK:
        _endpoints.clear()
        _recent_errors.clear()
        _slowest.clear()
