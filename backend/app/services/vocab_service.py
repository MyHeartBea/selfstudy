"""英语生词本：生词 CRUD、到期队列与闪卡复习排期。

排期规则（按掌握度阶梯 1/2/4/7/15/30/60 天）：
- 认识（known）：mastery + 1，间隔按阶梯拉长
- 模糊（fuzzy）：mastery 不变，明天再见
- 不认识（unknown）：mastery 归 0，立即再进队列
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import local_day_bounds_utc

# mastery_level（答对次数）→ 下次间隔天数
INTERVALS = [0, 1, 2, 4, 7, 15, 30, 60]
MAX_MASTERY = len(INTERVALS) - 1


def vocab_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_vocab_by_word(conn: sqlite3.Connection, word: str):
    return conn.execute(
        "SELECT * FROM vocab_items WHERE word = ? COLLATE NOCASE", (word,)
    ).fetchone()


def get_vocab(conn: sqlite3.Connection, vocab_id: int):
    return conn.execute(
        "SELECT * FROM vocab_items WHERE id = ?", (vocab_id,)
    ).fetchone()


def list_vocab(
    conn: sqlite3.Connection,
    search: Optional[str] = None,
    mastery: Optional[int] = None,
    page: Optional[int] = None,
    page_size: int = 20,
    sort: str = "created_desc",
) -> dict:
    """生词列表：搜索（词/释义/笔记）、掌握度筛选、分页与排序。"""
    where = []
    params: List[object] = []
    if search:
        where.append(
            "(word LIKE ? OR meaning LIKE ? OR note LIKE ? OR example LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])
    if mastery is not None:
        where.append("mastery_level = ?")
        params.append(mastery)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    order = {
        "created_desc": "created_at DESC, id DESC",
        "created_asc": "created_at ASC, id ASC",
        "mastery_asc": "mastery_level ASC, next_review_at ASC",
        "alpha": "word COLLATE NOCASE ASC",
    }.get(sort, "created_at DESC, id DESC")

    total = conn.execute(
        f"SELECT COUNT(*) FROM vocab_items {where_sql}", params
    ).fetchone()[0]

    if page is not None:
        rows = conn.execute(
            f"SELECT * FROM vocab_items {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, page_size, (page - 1) * page_size),
        ).fetchall()
        return {
            "items": [vocab_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    rows = conn.execute(
        f"SELECT * FROM vocab_items {where_sql} ORDER BY {order}", params
    ).fetchall()
    return [vocab_to_dict(row) for row in rows]


def create_vocab(
    conn: sqlite3.Connection,
    word: str,
    meaning: str = "",
    phonetic: str = "",
    example: str = "",
    note: str = "",
    source: str = "",
) -> sqlite3.Row:
    """新增生词；重复单词返回已有条目（幂等）。"""
    existing = get_vocab_by_word(conn, word)
    if existing is not None:
        return existing
    conn.execute(
        """
        INSERT INTO vocab_items (word, meaning, phonetic, example, note, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (word.strip(), meaning.strip(), phonetic.strip(), example.strip(), note.strip(), source.strip()),
    )
    conn.commit()
    return get_vocab_by_word(conn, word)


def update_vocab(conn: sqlite3.Connection, vocab_id: int, fields: dict) -> Optional[sqlite3.Row]:
    """更新生词（只更新传入字段）。"""
    allowed = ("word", "meaning", "phonetic", "example", "note", "source")
    sets = []
    params: List[object] = []
    for key in allowed:
        if key in fields and fields[key] is not None:
            sets.append(f"{key} = ?")
            params.append(str(fields[key]).strip())
    if not sets:
        return get_vocab(conn, vocab_id)
    params.append(vocab_id)
    conn.execute(
        f"UPDATE vocab_items SET {', '.join(sets)} WHERE id = ?", params
    )
    conn.commit()
    return get_vocab(conn, vocab_id)


def delete_vocab(conn: sqlite3.Connection, vocab_id: int) -> bool:
    cursor = conn.execute("DELETE FROM vocab_items WHERE id = ?", (vocab_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_due_vocab(conn: sqlite3.Connection, limit: int = 30) -> List[dict]:
    """今日到期（或从未安排）的生词，优先掌握度低的，随机顺序防位置记忆。"""
    start, end = local_day_bounds_utc()
    rows = conn.execute(
        """
        SELECT * FROM vocab_items
        WHERE next_review_at IS NULL
           OR next_review_at < ?
        ORDER BY mastery_level ASC, next_review_at ASC
        LIMIT ?
        """,
        (end, limit * 3),
    ).fetchall()
    items = [vocab_to_dict(row) for row in rows]
    import random

    random.shuffle(items)
    return items[:limit]


def vocab_stats(conn: sqlite3.Connection) -> dict:
    """生词总览：总数、各掌握度分布、今日到期数。"""
    start, end = local_day_bounds_utc()
    total = conn.execute("SELECT COUNT(*) FROM vocab_items").fetchone()[0]
    distribution = conn.execute(
        """
        SELECT mastery_level AS mastery, COUNT(*) AS count
        FROM vocab_items
        GROUP BY mastery_level
        ORDER BY mastery_level
        """
    ).fetchall()
    due = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE next_review_at IS NULL OR next_review_at < ?",
        (end,),
    ).fetchone()[0]
    mastered = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE mastery_level >= ?",
        (5,),
    ).fetchone()[0]
    return {
        "total": total,
        "due": due,
        "mastered": mastered,
        "distribution": [dict(row) for row in distribution],
    }


def review_vocab(conn: sqlite3.Connection, vocab_id: int, result: str) -> Optional[dict]:
    """闪卡复习结果：known / fuzzy / unknown。"""
    row = get_vocab(conn, vocab_id)
    if row is None:
        return None
    if result == "known":
        mastery = min(MAX_MASTERY, (row["mastery_level"] or 0) + 1)
    elif result == "unknown":
        mastery = 0
    else:
        mastery = row["mastery_level"] or 0

    if result == "known":
        interval = INTERVALS[mastery]
    elif result == "fuzzy":
        interval = 1
    else:
        interval = 0  # 立即再进队列

    next_review = None
    if interval > 0:
        next_review = (datetime.utcnow() + timedelta(days=interval)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    elif interval == 0 and result != "unknown":
        next_review = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        """
        UPDATE vocab_items
        SET mastery_level = ?,
            review_count = review_count + 1,
            wrong_count = wrong_count + ?,
            last_result = ?,
            last_reviewed_at = CURRENT_TIMESTAMP,
            next_review_at = ?
        WHERE id = ?
        """,
        (
            mastery,
            1 if result == "unknown" else 0,
            result,
            next_review if result != "unknown" else None,
            vocab_id,
        ),
    )
    conn.commit()
    return vocab_to_dict(get_vocab(conn, vocab_id))


def import_vocab(
    conn: sqlite3.Connection, lines: List[str], source: str = ""
) -> dict:
    """批量导入生词：每行「单词 释义」或「单词,释义」或「单词 —— 释义」，返回成功/失败明细。"""
    created = 0
    updated = 0
    failed: List[dict] = []
    for line_no, raw in enumerate(lines, start=1):
        text = (raw or "").strip()
        if not text:
            continue
        import re

        parts = (
            re.split(r"\s*[-—=]+\s*|\t|\s{2,}|,\s*", text, maxsplit=1)
            if len(text) > 1
            else [text]
        )
        if len(parts) == 1:
            parts = text.split(maxsplit=1)
        word = (parts[0] or "").strip()
        meaning = (parts[1] or "").strip() if len(parts) > 1 else ""
        if not word or not all(ch.isascii() or ch in "-'. " for ch in word):
            failed.append({"line": line_no, "text": text, "reason": "无法解析单词"})
            continue
        existing = get_vocab_by_word(conn, word)
        if existing is not None:
            if meaning and not existing["meaning"]:
                conn.execute(
                    "UPDATE vocab_items SET meaning = ? WHERE id = ?",
                    (meaning, existing["id"]),
                )
                updated += 1
            continue
        conn.execute(
            "INSERT INTO vocab_items (word, meaning, source) VALUES (?, ?, ?)",
            (word, meaning, source),
        )
        created += 1
    conn.commit()
    return {"created": created, "updated": updated, "failed": failed}
