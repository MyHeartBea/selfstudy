"""统计接口。"""

from fastapi import APIRouter

from app.database import get_connection
from app.responses import error, ok
from app.services import stats_service

router = APIRouter(prefix="/api", tags=["统计"])


@router.get("/stats")
def get_stats():
    """返回总错题数、今日新增和按科目统计。"""
    conn = get_connection()
    try:
        return ok(stats_service.get_stats(conn))
    except Exception as exc:
        return error(500, f"获取统计失败：{exc}")
    finally:
        conn.close()
