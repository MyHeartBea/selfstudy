"""冲刺计划接口：按考试日倒推的每日/每周目标（零 AI，纯统计）。"""

from fastapi import APIRouter

from app.database import get_connection
from app.responses import ok, server_error
from app.services import sprint_service

router = APIRouter(prefix="/api", tags=["冲刺计划"])


@router.get("/sprint/plan")
def sprint_plan():
    conn = get_connection()
    try:
        return ok(sprint_service.get_sprint_plan(conn))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
