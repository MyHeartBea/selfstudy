"""冲刺计划：按考试日倒推每天/每周该做多少，纯 SQL 统计，零 AI。

口径与今日复习队列一致（新题 = review_count=0 OR next_review_at IS NULL；
积压 = next_review_at < 明天），数字要能和复习页对上，不能各说各话。
"""

from __future__ import annotations

import datetime
import math
import re

from app.config import settings
from app.services import review_service


def _parse_exam_date(value: str):
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _tomorrow_iso(now: datetime.datetime) -> str:
    return (now.date() + datetime.timedelta(days=1)).isoformat()


def get_sprint_plan(conn) -> dict:
    now = datetime.datetime.now().astimezone()
    today = now.date()
    tomorrow = _tomorrow_iso(now)
    exam = _parse_exam_date(settings.EXAM_DATE)

    total_active = conn.execute(
        "SELECT COUNT(*) AS c FROM mistakes WHERE review_paused = 0"
    ).fetchone()["c"]
    due_now = conn.execute(
        "SELECT COUNT(*) AS c FROM mistakes WHERE review_paused = 0 "
        "AND next_review_at IS NOT NULL AND next_review_at < ?",
        (tomorrow,),
    ).fetchone()["c"]
    never_started = conn.execute(
        "SELECT COUNT(*) AS c FROM mistakes WHERE review_paused = 0 "
        "AND review_count = 0 AND next_review_at IS NULL"
    ).fetchone()["c"]
    reviewed_today = conn.execute(
        "SELECT COUNT(*) AS c FROM review_records WHERE date(reviewed_at) = date('now','localtime')"
    ).fetchone()["c"]

    plan = {
        "exam_date": settings.EXAM_DATE,
        "today": today.isoformat(),
        "days_left": None,
        "passed": False,
        "date_invalid": False,
        "total_active": total_active,
        "due_now": due_now,
        "never_started": never_started,
        "reviewed_today": reviewed_today,
        "daily_target": None,
        "quota_note": "",
        "subjects": [],
        "weeks": [],
    }
    if exam is None:
        plan["date_invalid"] = True
        return plan
    if exam < today:
        plan["passed"] = True
        return plan
    days_left = (exam - today).days
    plan["days_left"] = days_left

    work = due_now + never_started
    daily = math.ceil(work / days_left) if days_left > 0 else work
    plan["daily_target"] = daily

    # 与今日复习队列同口径：页内覆盖值优先（review_service.get_daily_limit）
    limit = review_service.get_daily_limit(conn)
    if limit and daily > limit:
        plan["quota_note"] = (
            f"按剩余天数平摊需要每天 {daily} 题，超过当前每日配额 {limit}——"
            "要么在复习页调大每日配额，要么接受清不完"
        )
    elif work == 0:
        plan["quota_note"] = "没有积压，按今日队列正常滚动即可"
    else:
        plan["quota_note"] = f"每天 {daily} 题，考前刚好过完一遍全部积压"

    subjects = conn.execute(
        """
        SELECT s.name AS name, COUNT(*) AS total,
               SUM(CASE WHEN m.next_review_at IS NOT NULL AND m.next_review_at < :tomorrow
                        THEN 1 ELSE 0 END) AS due,
               SUM(CASE WHEN m.review_count = 0 AND m.next_review_at IS NULL
                        THEN 1 ELSE 0 END) AS never,
               AVG(m.mastery_level) AS mastery
        FROM mistakes m JOIN subjects s ON s.id = m.subject_id
        WHERE m.review_paused = 0
        GROUP BY s.id
        ORDER BY due + never DESC, total DESC
        """,
        {"tomorrow": tomorrow},
    ).fetchall()
    plan["subjects"] = [
        {
            "name": r["name"],
            "total": r["total"],
            "due": r["due"] or 0,
            "never": r["never"] or 0,
            "mastery": round(r["mastery"] or 0),
        }
        for r in subjects
    ]

    # 剩余时间按周分桶：每周分到的量 = daily × 7（最后一周不足 7 天按实际天数）
    remaining = days_left
    week_no = 1
    while remaining > 0:
        span = min(7, remaining)
        end = today + datetime.timedelta(days=remaining)
        plan["weeks"].append(
            {
                "label": f"第 {week_no} 周",
                "days": span,
                "end_date": end.isoformat(),
                "target": daily * span,
            }
        )
        remaining -= span
        week_no += 1
    return plan
