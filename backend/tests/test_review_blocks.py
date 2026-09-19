"""复习分块的回归测试：今日队列按数学/408/英语/政治分块（墨韵 3.5）。

用户需求：今日复习默认只刷数学，同时提供 408 / 英语 / 政治的分类刷题。
分块靠科目名关键词归块（数学/408|计算机/英语/政治），配额仍是全局共享。
"""

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from app.models.tables import TABLES_DDL
from app.services import review_service


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    # 四个大块科目 + 一个不入块的杂项科目（模拟手工建的科目）
    for sid, name in [(1, "数学二"), (2, "408"), (3, "英语二"), (4, "政治"), (5, "杂项")]:
        conn.execute("INSERT INTO subjects (id, name) VALUES (?, ?)", (sid, name))
    conn.commit()
    return conn


NOW = datetime.now(timezone.utc)


def utc(delta_days: float) -> str:
    return (NOW + timedelta(days=delta_days)).strftime("%Y-%m-%d %H:%M:%S")


def add_mistake(conn, subject_id: int, question: str) -> int:
    cur = conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
        "analysis, difficulty, difficulty_points, knowledge_tags, source_type, "
        "mastery_level, review_count, wrong_count, ease_factor, last_interval, "
        "next_review_at, last_reviewed_at, created_at) "
        "VALUES (?, 'choice', ?, 'A', '解析', 3, '难点', '[]', 'other', "
        "1, 0, 0, 2.5, 0, NULL, NULL, ?)",
        (subject_id, question, utc(-30)),
    )
    conn.commit()
    return cur.lastrowid


class ReviewBlocksTest(unittest.TestCase):
    def test_today_queue_filters_by_block(self):
        """category=math 只返回数学系的题；不传 category 行为不变（全部科目）。"""
        conn = make_conn()
        add_mistake(conn, 1, "数学题")
        add_mistake(conn, 2, "408题")
        add_mistake(conn, 3, "英语题")
        add_mistake(conn, 4, "政治题")
        add_mistake(conn, 5, "杂项题")

        res = review_service.get_today_queue(conn, limit=50, daily_limit=0, category="math")
        self.assertEqual([it["question"] for it in res["items"]], ["数学题"])
        self.assertEqual(res["dueTotal"], 1)

        # 不传 category：所有题都在（含不入块的杂项）
        res_all = review_service.get_today_queue(conn, limit=50, daily_limit=0)
        self.assertEqual(res_all["dueTotal"], 5)

    def test_block_matches_subject_name_keywords(self):
        """归块按关键词包含：英语二归英语、计算机408 归 408、数学三归数学。"""
        conn = make_conn()
        conn.execute("INSERT INTO subjects (id, name) VALUES (6, '数学三')")
        conn.execute("INSERT INTO subjects (id, name) VALUES (7, '计算机408')")
        conn.commit()
        blocks = {b["key"]: b for b in review_service.get_review_blocks(conn)}
        # 数学块 = 数学二(1) + 数学三(6)，total 各 0（还没插题）
        self.assertIn("math", blocks)
        math_ids = review_service._subject_ids_for_block(conn, "math")
        self.assertIn(6, math_ids)
        cs_ids = review_service._subject_ids_for_block(conn, "cs408")
        self.assertIn(7, cs_ids)
        self.assertIn(2, cs_ids)
        en_ids = review_service._subject_ids_for_block(conn, "english")
        self.assertIn(3, en_ids)

    def test_blocks_summary_counts(self):
        """blocks 汇总：due 只数到期（含新题），total 数全部未暂停。"""
        conn = make_conn()
        add_mistake(conn, 1, "数学新题")  # 新题 = 到期
        add_mistake(conn, 1, "数学未到期")
        # 排到 30 天后且复习过（review_count=0 的题按设计永远算"到期未见过"）
        conn.execute(
            "UPDATE mistakes SET next_review_at = ?, review_count = 1 WHERE question = '数学未到期'",
            (utc(30),),
        )
        add_mistake(conn, 2, "408新题")
        add_mistake(conn, 5, "杂项题")
        conn.commit()

        blocks = {b["key"]: b for b in review_service.get_review_blocks(conn)}
        self.assertEqual(blocks["math"]["due"], 1)
        self.assertEqual(blocks["math"]["total"], 2)
        self.assertEqual(blocks["cs408"]["due"], 1)
        self.assertEqual(blocks["english"]["due"], 0)
        # 杂项科目不入块
        self.assertEqual(blocks["politics"]["total"], 0)
        all_due = sum(b["due"] for b in blocks.values())
        self.assertEqual(all_due, 2, "杂项题不进任何块")

    def test_empty_block_returns_empty_queue(self):
        """该块在库里没有科目/没有题：返回空队列而不是报错。"""
        conn = make_conn()
        add_mistake(conn, 1, "数学题")
        res = review_service.get_today_queue(conn, limit=50, daily_limit=0, category="politics")
        self.assertEqual(res["items"], [])
        self.assertEqual(res["dueTotal"], 0)
        self.assertEqual(res["remaining"], 0)

    def test_quota_is_global_across_blocks(self):
        """每日配额是全局的：跨块累计 reviewedToday，换块不重置额度。"""
        conn = make_conn()
        add_mistake(conn, 1, "数学题")
        add_mistake(conn, 2, "408题")
        # 今天已在数学块做了 1 题
        stamp = NOW.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO review_records (mistake_id, result, reviewed_at) VALUES (1, 'correct', ?)",
            (stamp,),
        )
        conn.commit()

        res_cs = review_service.get_today_queue(conn, limit=50, daily_limit=1, category="cs408")
        self.assertEqual(res_cs["reviewedToday"], 1, "reviewedToday 是全局的（含数学块做的 1 题）")
        self.assertEqual(res_cs["items"], [], "配额 1 已被数学块用完 → 408 块无可做题")


if __name__ == "__main__":
    unittest.main()
