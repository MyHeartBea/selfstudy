"""复习排期与复习记录业务逻辑。"""

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.config import settings
from app.database import local_day_bounds_utc, mistake_tag_condition, mistake_to_dict
from app.services.answer_service import judge_fill, judge_letters
from app.services.search_service import like_pattern

INTERVALS = [1, 3, 7, 15, 30]  # v5 旧固定阶梯：仅迁移回填/兼容保留

DAILY_LIMIT_META_KEY = "review_daily_limit"


def get_daily_limit(conn: sqlite3.Connection) -> int:
    """每日配额：页内覆盖值（app_meta）优先，未设置或非法时回退 .env 的 REVIEW_DAILY_LIMIT。"""
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (DAILY_LIMIT_META_KEY,),
    ).fetchone()
    if row and row["value"] not in (None, ""):
        try:
            return max(0, int(row["value"]))
        except (TypeError, ValueError):
            pass
    return int(settings.REVIEW_DAILY_LIMIT or 0)


def set_daily_limit(conn: sqlite3.Connection, value: int) -> int:
    """保存每日配额覆盖值（0 = 不限）；非法值抛 ValueError。"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("每日配额必须是非负整数") from None
    if value < 0:
        raise ValueError("每日配额必须是非负整数")
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (DAILY_LIMIT_META_KEY, str(value)),
    )
    conn.commit()
    return value


# SM-2 简化版参数
SM2_EASE_INIT = 2.5
SM2_EASE_MIN = 1.3
SM2_EASE_MAX = 2.8
SM2_MAX_INTERVAL = 180


def _next_schedule(ease: float, last_interval: int, result: bool):
    """SM-2 简化版：答对 → 间隔 = 上次间隔 × 难度系数（首次 1 天），系数 +0.1；
    答错 → 重置 1 天，系数 -0.2。返回 (新系数, 新间隔天数)。"""
    if result:
        interval = int(last_interval * ease + 0.5) if last_interval > 0 else 1
        interval = max(1, min(SM2_MAX_INTERVAL, interval))
        ease = min(SM2_EASE_MAX, ease + 0.1)
    else:
        interval = 1
        ease = max(SM2_EASE_MIN, ease - 0.2)
    return ease, interval


def _utc_to_local_datetime(value):
    """把数据库中的 UTC 时间转成本地时间，用于本地日期统计。"""
    text = str(value or "")[:19]
    try:
        return (
            datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone()
        )
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


def _expand_passage_items(data: List[dict]) -> List[dict]:
    """英语整篇（一条错题含多题）：复习时按「答错的题」逐题展开，每题一个复习项。

    若未标记答错（wrong 均非 true），则回退为展开全部题目，保证总是可复习。
    """
    out: List[dict] = []
    for item in data:
        qs = item.get("english_questions") or []
        if qs:
            wrong_qs = [q for q in qs if isinstance(q, dict) and q.get("wrong") is True]
            chosen = wrong_qs if wrong_qs else [q for q in qs if isinstance(q, dict)]
            if len(chosen) > 1:
                for q in chosen:
                    entry = dict(item)
                    for key in (
                        "question",
                        "question_type",
                        "option_a",
                        "option_b",
                        "option_c",
                        "option_d",
                        "option_e",
                        "option_f",
                        "option_g",
                        "correct_answer",
                        "analysis",
                        "difficulty",
                        "difficulty_points",
                        "approach",
                    ):
                        if q.get(key) is not None:
                            entry[key] = q[key]
                    entry["english_sub_question"] = True
                    out.append(entry)
                continue
        out.append(item)
    return out


def get_due_mistakes(
    conn: sqlite3.Connection,
    limit: int = 50,
    daily_limit: Optional[int] = None,
) -> List[dict]:
    """返回今日待复习错题（带每日配额与轮转，见 get_today_queue）。"""
    return get_today_queue(conn, limit=limit, daily_limit=daily_limit)["items"]


def _count_reviewed_today(conn: sqlite3.Connection) -> int:
    """今日已复习的条数（用于把每日配额算成"今天还能做多少"）。"""
    day_start_utc, day_end_utc = local_day_bounds_utc()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM review_records WHERE reviewed_at >= ? AND reviewed_at < ?",
        (day_start_utc, day_end_utc),
    ).fetchone()
    return int(row["c"] or 0)


# ── 复习分块（墨韵 3.5）─────────────────────────────────────────────────
# 今日复习按大类分块：默认只刷数学，同时提供 408 / 英语 / 政治。
# 科目名按**包含关键词**归块（subjects 表是小表，全量取回在 Python 里匹配），
# 兼容 数学/数学一/数学二/数学三、英语/英语一/英语二、408/计算机408、政治 等命名。
# 没有归入任何块的科目（如手工建的杂项科目）不会出现在四个分块里，
# 只能通过自主练习等模式触达 —— 这是刻意行为：分块是给四大主科用的。
REVIEW_BLOCKS = [
    {"key": "math", "name": "数学", "match": ("数学",)},
    {"key": "cs408", "name": "408", "match": ("408", "计算机")},
    {"key": "english", "name": "英语", "match": ("英语",)},
    {"key": "politics", "name": "政治", "match": ("政治",)},
]

VALID_REVIEW_BLOCKS = tuple(b["key"] for b in REVIEW_BLOCKS)


def _subject_ids_for_block(conn: sqlite3.Connection, category: str) -> Optional[List[int]]:
    """把分块 key 解析成科目 id 列表。

    返回 None = 不过滤（category 为空或不认识）；返回 [] = 该块在库里没有科目。
    """
    spec = next((b for b in REVIEW_BLOCKS if b["key"] == category), None)
    if not spec:
        return None
    rows = conn.execute("SELECT id, name FROM subjects").fetchall()
    return [int(r["id"]) for r in rows if any(m in (r["name"] or "") for m in spec["match"])]


def get_review_blocks(conn: sqlite3.Connection) -> List[dict]:
    """四个复习分块及各自的到期数：[{key, name, due, total}]。

    due = 该块今日到期（含从未复习的新题，与 get_today_queue 的 due 口径一致）；
    total = 该块错题总数（含未到期）。已暂停复习的题不计入。
    """
    due_map = {
        int(r["subject_id"]): int(r["c"])
        for r in conn.execute(
            "SELECT subject_id, COUNT(*) AS c FROM mistakes "
            "WHERE COALESCE(review_paused, 0) = 0 "
            "AND (next_review_at IS NULL OR next_review_at <= datetime('now') "
            "     OR review_count = 0) "
            "GROUP BY subject_id"
        ).fetchall()
    }
    total_map = {
        int(r["subject_id"]): int(r["c"])
        for r in conn.execute(
            "SELECT subject_id, COUNT(*) AS c FROM mistakes "
            "WHERE COALESCE(review_paused, 0) = 0 GROUP BY subject_id"
        ).fetchall()
    }
    subjects = conn.execute("SELECT id, name FROM subjects").fetchall()
    out = []
    for spec in REVIEW_BLOCKS:
        ids = [int(r["id"]) for r in subjects if any(m in (r["name"] or "") for m in spec["match"])]
        out.append(
            {
                "key": spec["key"],
                "name": spec["name"],
                "due": sum(due_map.get(i, 0) for i in ids),
                "total": sum(total_map.get(i, 0) for i in ids),
            }
        )
    return out


def get_today_queue(
    conn: sqlite3.Connection,
    limit: int = 50,
    daily_limit: Optional[int] = None,
    category: Optional[str] = None,
) -> dict:
    """今日复习队列：**新题优先 + 逾期轮转 + 每日配额**。

    为什么要这么排（原实现的问题）：
    原排序是「最旧的 next_review_at 最先」，于是 8 月答错、逾期 20 天的题永远霸占
    队列前排，8 月之后转好的题再也轮不到（实测 98/99 题为到期、16 题从未复习、
    55 题只复习过 0~1 次）——即越差的题越被反复刷，没暴露过的题一直饿着。

    现在的规则：
    1. **新题优先**：从未复习过（无 next_review_at 或 review_count=0）的题排最前，
       保证新录入的错题一定会被看到；
    2. **逾期轮转**：其余按 last_reviewed_at 升序（最久没碰过的先来）。复习一次
       last_reviewed_at 就刷新，该题自动排到队尾，于是整个积压会被像轮盘一样
       逐日推过一遍，而不是天天砸同几道题；
    3. **每日配额**：daily_limit（默认 settings.REVIEW_DAILY_LIMIT）是"今天总共
       做多少"，已减去今日已复习数——所以你做完就收工，不会无底洞；
    4. **不淘汰**：题不会被移出队列（没有"毕业/归档"），只是按顺序轮转；
    5. **分块**（category）：math/cs408/english/politics 四选一，只取该大类的题；
       配额仍是全局的（reviewedToday 跨块累计），换块不重置今日额度。

    返回 {"items", "dueTotal", "returned", "dailyLimit", "reviewedToday", "remaining"}：
    remaining 是今天做完这一批后该块还积压多少（dueTotal - 本批返回数）；
    传 category 时 dueTotal/remaining 只统计该块，每日配额仍是全局共享。
    """
    if daily_limit is None:
        daily_limit = get_daily_limit(conn)

    subject_ids = _subject_ids_for_block(conn, category) if category else None
    if category and subject_ids == []:
        # 该块没有科目：直接给空队列，不做全表查询
        reviewed_today = _count_reviewed_today(conn)
        return {
            "items": [],
            "dueTotal": 0,
            "returned": 0,
            "dailyLimit": int(daily_limit or 0),
            "reviewedToday": reviewed_today,
            "remaining": 0,
        }

    block_sql = ""
    block_params: tuple = ()
    if subject_ids is not None:
        marks = ",".join("?" for _ in subject_ids)
        block_sql = f"AND subject_id IN ({marks}) "
        block_params = tuple(subject_ids)

    due_total = int(
        conn.execute(
            "SELECT COUNT(*) AS c FROM mistakes "
            "WHERE COALESCE(review_paused, 0) = 0 "
            "AND (next_review_at IS NULL OR next_review_at <= datetime('now') "
            "     OR review_count = 0) " + block_sql,
            block_params,
        ).fetchone()["c"]
    )

    reviewed_today = _count_reviewed_today(conn)

    # 今天还能做多少：每日配额 - 今日已做
    budget = limit
    if daily_limit and daily_limit > 0:
        remaining_today = max(0, daily_limit - reviewed_today)
        budget = min(limit, remaining_today)

    rows = []
    if budget > 0:
        # 注意顺序：**先展开再截断**。英语整篇会被 _expand_passage_items 展开成多道小题，
        # 若先按 budget 截断行数再展开，实际题量会超过每日配额（实测 50 行 → 59 题）。
        # 这里多取一些候选行（英语整篇最多展开 4 项，取 3 倍余量足够），展开后再按配额截断。
        fetch = min(max(budget * 3, budget + 20), 300)
        rows = conn.execute(
            "SELECT * FROM mistakes "
            "WHERE COALESCE(review_paused, 0) = 0 "
            "AND (next_review_at IS NULL OR next_review_at <= datetime('now') "
            "     OR review_count = 0) " + block_sql + "ORDER BY "
            "  CASE WHEN review_count = 0 OR next_review_at IS NULL THEN 0 ELSE 1 END ASC, "
            "  COALESCE(last_reviewed_at, '1970-01-01 00:00:00') ASC, "
            "  COALESCE(next_review_at, '9999-12-31 23:59:59') ASC, "
            "  id ASC "
            "LIMIT ?",
            block_params + (fetch,),
        ).fetchall()

    items = (
        _expand_passage_items([mistake_to_dict(row) for row in rows])[:budget] if budget > 0 else []
    )
    return {
        "items": items,
        "dueTotal": due_total,
        "returned": len(items),
        "dailyLimit": int(daily_limit or 0),
        "reviewedToday": reviewed_today,
        "remaining": max(0, due_total - len(items)),
    }


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
    mistake_id: Optional[int] = None,
) -> List[dict]:
    """按记忆曲线、错误时间、随机或弱项组卷方式抽取错题进行自主练习。"""
    if mode in ("real_exam", "mock"):
        # 真题专项与真题模考同源：只取真题，其余条件照常生效
        mode = "curve"
        source_type = source_type or "real_exam"
    conditions = ["COALESCE(m.review_paused, 0) = 0"]
    params = []
    if mode == "weak":
        # 弱项组卷：从累计答错最多的前 5 个知识点里抽题（排序走默认的到期优先）。
        # 其他筛选条件（科目/题型等）照常叠加，方便"只刷数学的弱项"这类组合。
        weak_rows = conn.execute(
            "SELECT t.tag FROM mistake_tag_map t JOIN mistakes m ON m.id = t.mistake_id "
            "WHERE m.wrong_count > 0 GROUP BY t.tag ORDER BY SUM(m.wrong_count) DESC LIMIT 5"
        ).fetchall()
        tags = [r["tag"] for r in weak_rows]
        if not tags:
            return []
        placeholders = ", ".join("?" for _ in tags)
        conditions.append(
            f"m.id IN (SELECT mistake_id FROM mistake_tag_map WHERE tag IN ({placeholders}))"
        )
        params.extend(tags)
    if mistake_id is not None:
        # 单题直练（详情页「练这道题」入口）
        conditions.append("m.id = ?")
        params.append(mistake_id)
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
        conditions.append("m.question LIKE ? ESCAPE '\\'")
        params.append(like_pattern(search))
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
        sql += " ORDER BY COALESCE(last_wrong_at, m.created_at) ASC, m.id LIMIT ?"
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

    return _expand_passage_items(data)


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
    elif current.get("question_type") in ("choice", "multi") and user_answer:
        # 字母题也以服务端为准：前端只为即时反馈自己判一次分，两处口径一旦漂移
        # （重复字母、越界字母），错的就是写进 SM-2 队列的那条记录。
        result = judge_letters(user_answer, current.get("correct_answer") or "")["correct"]
    mastery = current.get("mastery_level") or 0
    review_count = current.get("review_count") or 0
    wrong_count = current.get("wrong_count") or 0
    ease = current.get("ease_factor") or SM2_EASE_INIT
    last_interval = current.get("last_interval") or 0

    if result:
        mastery = min(5, mastery + 1)
        # SM-2 简化版：间隔自适应拉长，越熟练的题复习得越稀疏
        ease, interval = _next_schedule(ease, last_interval, True)
    else:
        mastery = max(0, mastery - 1)
        wrong_count += 1
        ease, interval = _next_schedule(ease, last_interval, False)
    review_count += 1

    now = datetime.now(timezone.utc)
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    next_at = (now + timedelta(days=interval)).strftime("%Y-%m-%d %H:%M:%S")

    conn.execute(
        "UPDATE mistakes SET mastery_level = ?, review_count = ?, wrong_count = ?, "
        "ease_factor = ?, last_interval = ?, last_reviewed_at = ?, next_review_at = ? "
        "WHERE id = ?",
        (mastery, review_count, wrong_count, ease, interval, now_text, next_at, mistake_id),
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


SNOOZE_DAILY_LIMIT = 3
SNOOZE_META_PREFIX = "snooze_count_"


def snooze_remaining(conn: sqlite3.Connection) -> int:
    """今天还能"稍后再看"几次（按本地日期计数，跨天自然清零）。"""
    key = SNOOZE_META_PREFIX + datetime.now().astimezone().strftime("%Y-%m-%d")
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    used = int(row["value"]) if row and row["value"] else 0
    return max(0, SNOOZE_DAILY_LIMIT - used)


def snooze_mistake(conn: sqlite3.Connection, mistake_id: int) -> Optional[dict]:
    """把这道题推到明天同一时间再看：不改复习计数/掌握度，不占今日配额进度。

    每天限 SNOOZE_DAILY_LIMIT 次（防止无脑跳过导致队列永远刷不动）；
    超限抛 ValueError。返回 None 表示错题不存在。
    """
    row = conn.execute("SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    if row is None:
        return None
    used = SNOOZE_DAILY_LIMIT - snooze_remaining(conn)
    if used >= SNOOZE_DAILY_LIMIT:
        raise ValueError(f"今天的「稍后再看」已用完（每天 {SNOOZE_DAILY_LIMIT} 次），明天再来")
    today_key = SNOOZE_META_PREFIX + datetime.now().astimezone().strftime("%Y-%m-%d")
    next_at = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE mistakes SET next_review_at = ? WHERE id = ?",
        (next_at, mistake_id),
    )
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (today_key, str(used + 1)),
    )
    # 顺手清掉历史日期的计数键（weekly_report 缓存同款做法）
    conn.execute(
        "DELETE FROM app_meta WHERE key LIKE ? AND key != ?",
        (SNOOZE_META_PREFIX + "%", today_key),
    )
    conn.commit()
    return {"mistake_id": mistake_id, "remaining": snooze_remaining(conn)}


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
        {"mastery": level, "count": mastery_map.get(level, 0)} for level in range(6)
    ]

    # 薄弱知识点：走 mistake_tag_map 索引联表聚合（该表由写入路径同步维护、
    # 迁移时全量重建），替代对全表 knowledge_tags 的递归拆行。
    weak_rows = conn.execute(
        "SELECT t.tag AS tag, COUNT(*) AS mistake_count, "
        "COALESCE(SUM(m.wrong_count), 0) AS wrong_count "
        "FROM mistake_tag_map t JOIN mistakes m ON m.id = t.mistake_id "
        "WHERE m.wrong_count > 0 "
        "GROUP BY t.tag ORDER BY wrong_count DESC LIMIT 10"
    ).fetchall()
    weakest_tags = [
        {
            "tag_name": row["tag"],
            "wrong_count": row["wrong_count"],
            "mistake_count": row["mistake_count"],
        }
        for row in weak_rows
    ]

    today_local = datetime.now().astimezone().date()
    start_local = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=6)
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
        "SELECT subject_id, COUNT(*) AS mistake_count FROM mistakes GROUP BY subject_id"
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
    subject_names = conn.execute("SELECT id, name FROM subjects ORDER BY id").fetchall()
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
                "accuracy": (round(correct_count / review_count * 100, 1) if review_count else 0.0),
            }
        )

    # 错因杠杆榜：按"累计答错次数"排序——谁贡献的丢分多谁在前。
    # error_reason 是复习答错后用户手动标的（mistake_service.ERROR_REASONS），
    # 机器判不出"为什么错"，这是错题本里唯一必须人承认的一维。
    error_reason_rows = conn.execute(
        """
        SELECT m.error_reason AS reason,
               COUNT(*) AS mistake_count,
               COALESCE(SUM((
                   SELECT COUNT(*) FROM review_records r
                   WHERE r.mistake_id = m.id AND r.result = 'wrong'
               )), 0) AS wrong_count
        FROM mistakes m
        WHERE m.error_reason != ''
        GROUP BY m.error_reason
        ORDER BY wrong_count DESC, mistake_count DESC
        """
    ).fetchall()

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
        "error_reasons": [dict(row) for row in error_reason_rows],
    }


def _forecast_bounds(days: int) -> tuple:
    """把「按天比较」翻译成定宽字符串的「按范围比较」，让 `idx_mistakes_next_review_at` 用得上。

    原来两句都写成 `date(next_review_at) < date('now','localtime')`：列被套进函数里，
    SQLite 拿不到索引，只能整表 SCAN。`next_review_at` 是 ISO 文本（'%Y-%m-%d %H:%M:%S'，
    见 review_service 的写入），日期前缀定宽，所以**日期串本身**就是干净的边界：
      date(x) >= D  ⟺  x >= 'D'      （x 以 D 开头时 x >= D；date(x) < D 时 x < D）
      date(x) <= D  ⟺  x < 'D+1天'
    逐行结果与改前一致（只有日期的 '2026-09-20'、带 T 的写法同样成立；NULL 两边都不命中）。
    """
    today = datetime.now().astimezone().date()
    return (today.isoformat(), (today + timedelta(days=days + 1)).isoformat())


def forecast_items(conn: sqlite3.Connection, days: int = 30) -> dict:
    """未来 N 天复习负荷分布：{overdue, items:[{day, count}]}（day=YYYY-MM-DD，含今日）。

    /api/dashboard 聚合与 /reviews/forecast 端点共用这一份实现，别再各写一份。
    """
    lo, hi = _forecast_bounds(days)
    overdue = conn.execute(
        "SELECT COUNT(*) AS c FROM mistakes WHERE review_paused = 0 AND next_review_at < ?",
        (lo,),
    ).fetchone()["c"]
    # GROUP BY day 用别名：day 是 date(next_review_at)，SQLite 允许按输出列分组
    rows = conn.execute(
        """
        SELECT date(next_review_at) AS day, COUNT(*) AS count
        FROM mistakes
        WHERE review_paused = 0 AND next_review_at >= ? AND next_review_at < ?
        GROUP BY day
        ORDER BY day
        """,
        (lo, hi),
    ).fetchall()
    return {"overdue": overdue, "items": [dict(row) for row in rows]}


def recent_mocks(conn: sqlite3.Connection, limit: int = 12) -> list:
    """模考成绩存档（按时间倒序），统计页画分数趋势用。"""
    rows = conn.execute(
        "SELECT * FROM mock_records ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
