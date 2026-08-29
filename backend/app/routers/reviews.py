"""复习相关接口。"""

from typing import Optional

from fastapi import APIRouter, Query

from app.database import get_connection
from app.responses import error, ok, server_error
from app.schemas import ReviewCreate
from app.services import review_service

router = APIRouter(prefix="/api", tags=["复习"])


@router.get("/reviews/today")
def get_today_reviews(limit: int = Query(50, ge=1, le=200)):
    """返回今日待复习错题。"""
    conn = get_connection()
    try:
        return ok(review_service.get_due_mistakes(conn, limit))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/reviews/calendar")
def get_review_calendar(days: int = Query(140, ge=14, le=366)):
    """按天聚合的复习记录（热力图数据）：[{day, total, correct}]。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT date(reviewed_at) AS day,
                   COUNT(*) AS total,
                   SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END) AS correct
            FROM review_records
            WHERE reviewed_at >= datetime('now', ?)
            GROUP BY date(reviewed_at)
            ORDER BY day
            """,
            (f"-{days} days",),
        ).fetchall()
        return ok([dict(row) for row in rows])
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/reviews/practice")
def get_practice_reviews(
    mode: str = Query("curve", pattern="^(curve|wrong_time|random|real_exam)$"),
    count: int = Query(10, ge=1, le=100),
    subject_id: Optional[int] = Query(None),
    sub_subject_id: Optional[int] = Query(None),
    question_type: Optional[str] = Query(None),
    difficulty: Optional[int] = Query(None, ge=1, le=5),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    source_year: Optional[str] = Query(None),
):
    """返回自主练习队列：记忆曲线、按错误时间或随机抽题。"""
    conn = get_connection()
    try:
        data = review_service.get_practice_mistakes(
            conn,
            mode=mode,
            count=count,
            subject_id=subject_id,
            sub_subject_id=sub_subject_id,
            question_type=question_type,
            difficulty=difficulty,
            tag=tag,
            search=search,
            source_type=source_type,
            source_year=source_year,
        )
        return ok(data)
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.post("/mistakes/{mistake_id}/review")
def review_mistake(mistake_id: int, body: ReviewCreate):
    """记录一次复习结果并自动安排下次复习。"""
    conn = get_connection()
    try:
        data = review_service.review_mistake(
            conn,
            mistake_id,
            body.result,
            body.note,
            body.user_answer,
        )
        if data is None:
            return error(404, "错题不存在")
        return ok(data, "复习记录已保存")
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()


@router.get("/reviews/stats")
def get_review_stats():
    """返回复习统计与薄弱知识点。"""
    conn = get_connection()
    try:
        return ok(review_service.get_review_stats(conn))
    except Exception as exc:
        return server_error(exc)
    finally:
        conn.close()
