"""系统级接口：健康检查与仪表盘聚合数据。"""

import platform
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.database import get_connection
from app.responses import ok, server_error
from app.services import review_service, stats_service

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
def health():
    """轻量健康检查：供前端状态灯与脚本探活使用。"""
    conn = get_connection()
    try:
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        conn.close()
    return ok(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "version": settings.VERSION,
            "app": settings.APP_NAME,
            "python": platform.python_version(),
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/dashboard")
def dashboard():
    """仪表盘聚合：一次请求返回错题统计 + 复习统计，减少首屏往返。"""
    conn = get_connection()
    try:
        return ok(
            {
                "stats": stats_service.get_stats(conn),
                "reviews": review_service.get_review_stats(conn),
            }
        )
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
