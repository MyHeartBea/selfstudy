"""复习排期与复习记录业务逻辑。"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.database import local_day_bounds_utc, mistake_tag_condition, mistake_to_dict
from app.services.answer_service import judge_fill

INTERVALS = [1, 3, 7, 15, 30]


def _utc_to_local_datetime(value):
    """把数据库中的 UTC 时间转成本地时间，用于本地日期统计。"""
    text = str(value or "")[:19]
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        ).astimezone()
    except ValueError:
        return None


def _days_between(value, now_text: str):
    """计算两个 UTC 时间字符串之间相差的天数，异常时返回 None。"""
    try:
        start = datetime.strptime(str(value or "")[:19], "%Y-%m-%d %H:%M:%S")
        now = datetime.strptime(now_text, "%Y-%m-%d %H:%M:%S")
        return max(0, (now - start).days)
    except (TypeError, ValueError):
        return None


def get_due_mistakes(conn: sqlite3.Connection, limit: int = 50) -> List[dict]:
    """返回今日待复习错题：新录入的错题优先，其次按下次复习时间升序。"""
    rows = conn.execute(
        "SELECT * FROM mistakes "
        "WHERE COALESCE(review_paused, 0) = 0 "
        "AND (next_review_at IS NULL OR next_review_at <= datetime('now')) "
        "ORDER BY (next_review_at IS NULL) DESC, "
        "COALESCE(next_review_at, '9999-12-31 23:59:59') ASC, id ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [mistake_to_dict(row) for row in rows]


def get_practice_mistakes(
    conn: sqlite3.Connection,
    mode: str = "curve",
    count: int = 10,
    subject_id: Optional[int] = None,
    sub_subject_id: Optional[int] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[int] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    source_type: Optional[str] = None,
    source_year: Optional[str] = None,
) -> List[dict]:
    """按记忆曲线、错误时间或随机方式抽取错题进行自主练习。"""
    if mode == "real_exam":
        mode = "curve"
        source_type = source_type or "real_exam"
    conditions = ["COALESCE(m.review_paused, 0) = 0"]
    params = []
    if subject_id is not None:
        conditions.append("m.subject_id = ?")
        params.append(subject_id)
    if sub_subject_id is not None:
        conditions.append("m.sub_subject_id = ?")
        params.append(sub_subject_id)
    if question_type:
        conditions.append("m.question_type = ?")
        params.append(question_type)
    if difficulty is not None:
        conditions.append("m.difficulty = ?")
        params.append(difficulty)
    if tag:
        tag = tag.strip()
        conditions.append(mistake_tag_condition())
        params.append(tag)
    if search:
        conditions.append("m.question LIKE ?")
        params.append(f"%{search}%")
    if source_type:
        conditions.append("m.source_type = ?")
        params.append(source_type)
    if source_year:
        conditions.append("m.source_year = ?")
        params.append(source_year)

    sql = (
        "SELECT m.*, "
        "r.last_wrong_at, r.last_reviewed_at "
        "FROM mistakes m "
        "LEFT JOIN ("
        "  SELECT mistake_id, "
        "  MAX(CASE WHEN result = 'wrong' THEN reviewed_at END) AS last_wrong_at, "
        "  MAX(reviewed_at) AS last_reviewed_at "
        "  FROM review_records GROUP BY mistake_id"
        ") r ON r.mistake_id = m.id WHERE " + " AND ".join(conditions)
    )
    limit = max(1, count)
    if mode == "random":
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
    elif mode == "wrong_time":
        sql += (
            " ORDER BY COALESCE(last_wrong_at, m.created_at) ASC, m.id LIMIT ?"
        )
        params.append(limit)
    else:
        sql += (
            " ORDER BY "
            "CASE WHEN COALESCE(next_review_at, '0000-01-01 00:00:00') "
            "<= datetime('now') THEN 0 ELSE 1 END, "
            "COALESCE(next_review_at, '0000-01-01 00:00:00') ASC, "
            "COALESCE(last_wrong_at, '9999-12-31 23:59:59') ASC, "
            "m.id LIMIT ?"
        )
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    data = [mistake_to_dict(row) for row in rows]
    now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for item in data:
        wrong_at = item.get("last_wrong_at") or item.get("created_at")
        item["last_wrong_at"] = wrong_at
        item["days_since_wrong"] = _days_between(wrong_at, now_text)
        item["days_since_review"] = _days_between(
            item.get("last_reviewed_at"),
            now_text,
        )

    return data


def review_mistake(
    conn: sqlite3.Connection,
    mistake_id: int,
    result: bool,
    note: str = "",
    user_answer: str = "",
) -> Optional[dict]:
    """记录一次复习结果，并按间隔重复算法安排下次复习。"""
    row = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    if row is None:
        return None

    current = dict(row)
    if current.get("question_type") == "fill" and user_answer:
        judge = judge_fill(
            user_answer,
            current.get("correct_answer") or "",
            current.get("answer_aliases") or "",
        )
        result = judge["correct"]
        note_parts = [note or "", f"你的答案：{user_answer}"]
        note = "；".join(part for part in note_parts if part)
    mastery = current.get("mastery_level") or 0
    review_count = current.get("review_count") or 0
    wrong_count = current.get("wrong_count") or 0

    if result:
        mastery = min(5, mastery + 1)
        # 递增前取档：首次答对（0→1）1 天后复习，之后 3/7/15/30 天逐级拉长
        interval = INTERVALS[max(0, mastery - 1)]
    else:
        mastery = max(0, mastery - 1)
        wrong_count += 1
        interval = 1
    review_count += 1

    now = datetime.now(timezone.utc)
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    next_at = (now + timedelta(days=interval)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    conn.execute(
        "UPDATE mistakes SET mastery_level = ?, review_count = ?, wrong_count = ?, "
        "last_reviewed_at = ?, next_review_at = ? WHERE id = ?",
        (mastery, review_count, wrong_count, now_text, next_at, mistake_id),
    )
    conn.execute(
        "INSERT INTO review_records (mistake_id, result, note, user_answer, reviewed_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            mistake_id,
            "correct" if result else "wrong",
            note or "",
            user_answer or "",
            now_text,
        ),
    )
    conn.commit()

    updated = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    return mistake_to_dict(updated)


def get_review_history(
    conn: sqlite3.Connection,
    mistake_id: int,
    limit: int = 30,
) -> List[dict]:
    """返回单道错题的复习记录，按时间倒序。"""
    rows = conn.execute(
        "SELECT id, result, note, user_answer, reviewed_at FROM review_records "
        "WHERE mistake_id = ? ORDER BY reviewed_at DESC, id DESC LIMIT ?",
        (mistake_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _compute_streak(conn: sqlite3.Connection) -> int:
    """计算连续复习天数：今天有记录则从今天算，否则从昨天算。"""
    # 只取最近 400 天内的去重时间戳，避免全表扫描无限增长
    rows = conn.execute(
        "SELECT DISTINCT reviewed_at FROM review_records "
        "WHERE reviewed_at >= datetime('now', '-400 days')"
    ).fetchall()
    days = []
    for row in rows:
        local = _utc_to_local_datetime(row["reviewed_at"])
        if local is not None:
            days.append(local.date().isoformat())
    days = sorted(set(days))
    if not days:
        return 0

    cursor = datetime.now().date()
    if days[-1] != cursor.isoformat():
        cursor -= timedelta(days=1)
    if days[-1] != cursor.isoformat():
        return 0

    streak = 0
    day_set = set(days)
    while cursor.isoformat() in day_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_review_stats(conn: sqlite3.Connection) -> dict:
    """返回复习统计：待复习数、今日完成、正确率、连续天数、薄弱知识点等。"""
    day_start_utc, day_end_utc = local_day_bounds_utc()
    due = conn.execute(
        "SELECT COUNT(*) FROM mistakes "
        "WHERE COALESCE(review_paused, 0) = 0 "
        "AND (next_review_at IS NULL OR next_review_at <= datetime('now'))"
    ).fetchone()[0]
    today_row = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END), 0) AS correct "
        "FROM review_records WHERE reviewed_at >= ? AND reviewed_at < ?",
        (day_start_utc, day_end_utc),
    ).fetchone()
    reviewed_today = today_row["total"]
    correct_today = today_row["correct"]
    totals = conn.execute(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END), 0) AS correct "
        "FROM review_records"
    ).fetchone()
    total_correct = totals["correct"]
    total_reviews = totals["total"]
    avg_mastery = conn.execute(
        "SELECT ROUND(COALESCE(AVG(mastery_level), 0), 2) FROM mistakes"
    ).fetchone()[0]
    mastery_rows = conn.execute(
        "SELECT mastery_level, COUNT(*) AS count FROM mistakes GROUP BY mastery_level"
    ).fetchall()
    mastery_map = {row["mastery_level"]: row["count"] for row in mastery_rows}
    mastery_distribution = [
        {"mastery": level, "count": mastery_map.get(level, 0)}
        for level in range(6)
    ]

    # 薄弱知识点：用递归 CTE 把 knowledge_tags 拆行后全量按标签聚合，
    # 不再只统计 wrong_count 前 30 行错题，结果完整准确。
    weak_rows = conn.execute(
        "WITH RECURSIVE split(mistake_id, wrong_count, tag, rest) AS ("
        "  SELECT id, wrong_count, '', knowledge_tags || ',' FROM mistakes WHERE wrong_count > 0"
        "  UNION ALL"
        "  SELECT mistake_id, wrong_count,"
        "         substr(rest, 1, instr(rest, ',') - 1),"
        "         substr(rest, instr(rest, ',') + 1)"
        "  FROM split WHERE rest != ''"
        ") "
        "SELECT tag, COUNT(*) AS mistake_count, SUM(wrong_count) AS wrong_count "
        "FROM split WHERE tag != '' GROUP BY tag "
        "ORDER BY wrong_count DESC LIMIT 10"
    ).fetchall()
    weakest_tags = [
        {"tag_name": row["tag"], "wrong_count": row["wrong_count"], "mistake_count": row["mistake_count"]}
        for row in weak_rows
    ]

    today_local = datetime.now().astimezone().date()
    start_local = (
        datetime.now()
        .astimezone()
        .replace(hour=0, minute=0, second=0, microsecond=0)
        - timedelta(days=6)
    )
    start_utc = start_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    day_map = {
        (today_local - timedelta(days=i)).isoformat(): {
            "day": (today_local - timedelta(days=i)).isoformat(),
            "count": 0,
            "correct": 0,
        }
        for i in range(6, -1, -1)
    }
    last_7_rows = conn.execute(
        "SELECT reviewed_at, result FROM review_records WHERE reviewed_at >= ?",
        (start_utc,),
    ).fetchall()
    for row in last_7_rows:
        local = _utc_to_local_datetime(row["reviewed_at"])
        if local is None:
            continue
        day_key = local.date().isoformat()
        if day_key in day_map:
            day_map[day_key]["count"] += 1
            if row["result"] == "correct":
                day_map[day_key]["correct"] += 1
    last_7_rows = list(day_map.values())

    # 各科目复习情况：两个独立聚合再合并，避免 subjects×mistakes×review_records 三表
    # join 把每道错题的每条复习记录放大成一行。
    subject_mistakes = conn.execute(
        "SELECT subject_id, COUNT(*) AS mistake_count "
        "FROM mistakes GROUP BY subject_id"
    ).fetchall()
    mistake_map = {row["subject_id"]: row["mistake_count"] for row in subject_mistakes}
    subject_reviews = conn.execute(
        "SELECT m.subject_id, COUNT(r.id) AS review_count, "
        "COALESCE(SUM(CASE WHEN r.result = 'correct' THEN 1 ELSE 0 END), 0) AS correct_count, "
        "COALESCE(SUM(CASE WHEN r.result = 'wrong' THEN 1 ELSE 0 END), 0) AS wrong_count "
        "FROM review_records r JOIN mistakes m ON m.id = r.mistake_id "
        "GROUP BY m.subject_id"
    ).fetchall()
    review_map = {row["subject_id"]: row for row in subject_reviews}
    subject_names = conn.execute(
        "SELECT id, name FROM subjects ORDER BY id"
    ).fetchall()
    by_subject_rows = []
    for subject in subject_names:
        sid = subject["id"]
        reviews_row = review_map.get(sid)
        review_count = reviews_row["review_count"] if reviews_row else 0
        correct_count = reviews_row["correct_count"] if reviews_row else 0
        wrong_count = reviews_row["wrong_count"] if reviews_row else 0
        by_subject_rows.append(
            {
                "subject_id": sid,
                "name": subject["name"],
                "mistake_count": mistake_map.get(sid, 0),
                "review_count": review_count,
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "accuracy": (
                    round(correct_count / review_count * 100, 1)
                    if review_count
                    else 0.0
                ),
            }
        )

    return {
        "due_today": due,
        "reviewed_today": reviewed_today,
        "accuracy_today": round(correct_today / reviewed_today * 100, 1) if reviewed_today else 0.0,
        "total_accuracy": round(total_correct / total_reviews * 100, 1) if total_reviews else 0.0,
        "avg_mastery": avg_mastery,
        "total_reviews": total_reviews,
        "streak_days": _compute_streak(conn),
        "mastery_distribution": mastery_distribution,
        "weakest_tags": weakest_tags,
        "last_7_days": [dict(row) for row in last_7_rows],
        "by_subject": by_subject_rows,
    }
