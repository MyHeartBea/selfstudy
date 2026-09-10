"""系统级接口：健康检查与仪表盘聚合数据。"""

import platform
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app import metrics
from app.config import settings
from app.database import get_connection, list_snapshots, snapshot_database
from app.responses import ok, server_error
from app.services import review_service, stats_service

router = APIRouter(prefix="/api", tags=["系统"])


@router.get("/health")
def health():
    """轻量健康检查：供前端状态灯与脚本探活使用。

    附带进程内监控摘要（请求数/错误数/慢端点），便于一眼看出哪里慢、有没有 5xx。
    """
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
            "host": settings.HOST,
            "reviewDailyLimit": settings.REVIEW_DAILY_LIMIT,
            "metrics": metrics.snapshot(),
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


@router.get("/snapshots")
def get_snapshots(limit: int = Query(20, ge=1, le=100)):
    """最近的数据快照列表（启动自动备份 + 导入前快照）。"""
    try:
        return ok(list_snapshots(limit))
    except Exception as exc:
        return server_error(exc)


@router.post("/snapshots")
def create_snapshot(label: str = Query("manual", max_length=40)):
    """手动打一份数据快照（批量导入/删除前建议先点一下）。"""
    name = snapshot_database(label)
    if not name:
        return error(500, "快照创建失败")
    return ok({"name": name}, "快照已创建")
