"""统计相关业务逻辑。"""

import sqlite3

from app.database import local_day_bounds_utc


def get_stats(conn: sqlite3.Connection) -> dict:
    """返回总错题数、今日新增和按科目统计。"""
    total = conn.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0]
    day_start_utc, day_end_utc = local_day_bounds_utc()
    today_new = conn.execute(
        "SELECT COUNT(*) FROM mistakes WHERE created_at >= ? AND created_at < ?",
        (day_start_utc, day_end_utc),
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT s.id AS subject_id, s.name AS name, "
        "COUNT(m.id) AS count, "
        "ROUND(COALESCE(AVG(m.difficulty), 0), 2) AS avg_difficulty "
        "FROM subjects s "
        "LEFT JOIN mistakes m ON m.subject_id = s.id "
        "GROUP BY s.id, s.name ORDER BY s.id"
    ).fetchall()
    sub_rows = conn.execute(
        "SELECT ss.subject_id AS subject_id, ss.id AS sub_subject_id, ss.name AS name, "
        "s.name AS subject_name, COUNT(m.id) AS count, "
        "ROUND(COALESCE(AVG(m.difficulty), 0), 2) AS avg_difficulty "
        "FROM sub_subjects ss "
        "JOIN subjects s ON s.id = ss.subject_id "
        "LEFT JOIN mistakes m ON m.sub_subject_id = ss.id "
        "GROUP BY ss.id, ss.name, ss.subject_id, s.name "
        "ORDER BY ss.subject_id, ss.id"
    ).fetchall()
    type_rows = conn.execute(
        "SELECT question_type, COUNT(*) AS count FROM mistakes GROUP BY question_type"
    ).fetchall()
    type_map = {row["question_type"]: row["count"] for row in type_rows}
    by_question_type = [
        {
            "question_type": key,
            "name": name,
            "count": type_map.get(key, 0),
        }
        for key, name in (("choice", "选择题"), ("fill", "填空题"), ("solution", "解答题"))
    ]
    source_rows = conn.execute(
        "SELECT source_type, COUNT(*) AS count FROM mistakes GROUP BY source_type"
    ).fetchall()
    source_map = {row["source_type"]: row["count"] for row in source_rows}
    by_source_type = [
        {
            "source_type": key,
            "name": name,
            "count": source_map.get(key, 0),
        }
        for key, name in (
            ("real_exam", "真题"),
            ("mock", "模拟题"),
            ("other", "自编/其他"),
        )
    ]
    return {
        "total_mistakes": total,
        "today_new": today_new,
        "by_subject": [dict(row) for row in rows],
        "by_sub_subject": [dict(row) for row in sub_rows],
        "by_question_type": by_question_type,
        "by_source_type": by_source_type,
    }
