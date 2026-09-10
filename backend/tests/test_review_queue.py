"""复习队列改造的回归测试：新题优先 / 逾期轮转 / 每日配额（不做毕业机制）。

覆盖用户实测暴露的问题：
- 98/99 题同时到期，队列按"最旧的 next_review_at 最先"排序，
  导致永远刷同几道最烂的题，新录入的题（next_review_at 为空）排在最后、
  以及"只复习过 0~1 次"的题再也轮不到。
"""

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from app.database import local_day_bounds_utc
from app.models.tables import TABLES_DDL
from app.services import review_service


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.execute("INSERT INTO subjects (id, name) VALUES (1, '测试科目')")
    conn.commit()
    return conn


NOW = datetime.now(timezone.utc)


def utc(delta_days: float) -> str:
    return (NOW + timedelta(days=delta_days)).strftime("%Y-%m-%d %H:%M:%S")


def add_mistake(
    conn,
    question: str,
    *,
    next_review_at=None,
    last_reviewed_at=None,
    review_count=0,
    paused=0,
) -> int:
    cur = conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
        "analysis, difficulty, difficulty_points, knowledge_tags, source_type, "
        "mastery_level, review_count, wrong_count, ease_factor, last_interval, "
        "review_paused, next_review_at, last_reviewed_at, created_at) "
        "VALUES (1, 'choice', ?, 'A', '解析', 3, '难点', '[]', 'other', "
        "1, ?, 0, 2.5, 0, ?, ?, ?, ?)",
        (question, review_count, paused, next_review_at, last_reviewed_at, utc(-30)),
    )
    conn.commit()
    return cur.lastrowid


class TodayQueueTest(unittest.TestCase):
    def test_new_items_come_first(self):
        """从未复习过的题（next_review_at 为空）必须排最前，而不是最后。"""
        conn = make_conn()
        # 一道逾期很久的旧题
        add_mistake(
            conn, "旧题", next_review_at=utc(-20), last_reviewed_at=utc(-25), review_count=3
        )
        # 一道新录入、从未复习的题
        add_mistake(conn, "新题", next_review_at=None, last_reviewed_at=None, review_count=0)

        res = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        questions = [it["question"] for it in res["items"]]
        self.assertEqual(questions[0], "新题", f"新题应优先，实际顺序 {questions}")

    def test_overdue_rotates_by_last_reviewed(self):
        """逾期题按"最久没碰过"排序；复习一次后会排到队尾（轮转而非天天同一批）。"""
        conn = make_conn()
        old = add_mistake(
            conn, "很久没碰", next_review_at=utc(-20), last_reviewed_at=utc(-25), review_count=3
        )
        recent = add_mistake(
            conn, "刚碰过", next_review_at=utc(-1), last_reviewed_at=utc(-2), review_count=3
        )

        res = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        order = [it["id"] for it in res["items"]]
        self.assertEqual(order, [old, recent], "应最久没碰过的优先")

        # 模拟复习「很久没碰」那道：last_reviewed_at 刷新 → 它应退到队尾
        conn.execute(
            "UPDATE mistakes SET last_reviewed_at = ?, next_review_at = ? WHERE id = ?",
            (utc(0), utc(-1), old),
        )
        conn.commit()
        res2 = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        order2 = [it["id"] for it in res2["items"]]
        self.assertEqual(order2[0], recent, "复习过的题应排到后面，另一道轮上来")

    def test_daily_limit_caps_and_subtracts_reviewed_today(self):
        """每日配额是"今天总共做多少"，要减去今日已复习数。"""
        conn = make_conn()
        for i in range(10):
            add_mistake(conn, f"题{i}", next_review_at=None, review_count=0)

        res = review_service.get_today_queue(conn, limit=99, daily_limit=4)
        self.assertEqual(len(res["items"]), 4)
        self.assertEqual(res["dailyLimit"], 4)
        self.assertEqual(res["reviewedToday"], 0)
        self.assertEqual(res["dueTotal"], 10)
        self.assertEqual(res["remaining"], 6)

        # 今天已复习 3 条 → 只剩 1 个名额
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for i in range(3):
            conn.execute(
                "INSERT INTO review_records (mistake_id, result, reviewed_at) VALUES (?, 'correct', ?)",
                (i + 1, stamp),
            )
        conn.commit()
        res2 = review_service.get_today_queue(conn, limit=99, daily_limit=4)
        self.assertEqual(res2["reviewedToday"], 3)
        self.assertEqual(len(res2["items"]), 1, "配额 4 - 已做 3 = 只剩 1")

    def test_daily_limit_zero_means_unlimited(self):
        conn = make_conn()
        for i in range(7):
            add_mistake(conn, f"题{i}", next_review_at=None, review_count=0)
        res = review_service.get_today_queue(conn, limit=5, daily_limit=0)
        self.assertEqual(len(res["items"]), 5, "0=不限制，只受 limit 约束")

    def test_paused_excluded(self):
        conn = make_conn()
        add_mistake(conn, "暂停题", next_review_at=None, review_count=0, paused=1)
        add_mistake(conn, "正常题", next_review_at=None, review_count=0)
        res = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        self.assertEqual([it["question"] for it in res["items"]], ["正常题"])

    def test_no_graduation_items_never_drop_out(self):
        """明确不做毕业机制：无论复习多少次、间隔多长，题都不会被移出候选。

        答错的题重置为 1 天 → 明天仍会到期并重新出现（这是设计要求，不是 bug）。
        """
        conn = make_conn()
        mid = add_mistake(
            conn, "老题", next_review_at=utc(-1), last_reviewed_at=utc(-30), review_count=20
        )
        res = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        self.assertIn(mid, [it["id"] for it in res["items"]])

        # 再答对很多次也不会消失（没有毕业/归档逻辑）
        conn.execute(
            "UPDATE mistakes SET review_count = 100, ease_factor = 2.8, last_interval = 180 WHERE id = ?",
            (mid,),
        )
        conn.commit()
        # 把它排到未来 → 今天不该出现；但到期后仍在队列里（不淘汰）
        conn.execute("UPDATE mistakes SET next_review_at = ? WHERE id = ?", (utc(90), mid))
        conn.commit()
        res_future = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        self.assertNotIn(mid, [it["id"] for it in res_future["items"]])

        conn.execute("UPDATE mistakes SET next_review_at = ? WHERE id = ?", (utc(-1), mid))
        conn.commit()
        res_back = review_service.get_today_queue(conn, limit=10, daily_limit=0)
        self.assertIn(mid, [it["id"] for it in res_back["items"]], "到期后仍回到队列（不毕业）")

    def test_backward_compatible_get_due_mistakes(self):
        """旧调用点（get_due_mistakes）仍返回列表，不破坏既有调用。"""
        conn = make_conn()
        add_mistake(conn, "题", next_review_at=None, review_count=0)
        items = review_service.get_due_mistakes(conn, limit=10)
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 1)

    def test_daily_limit_holds_after_passage_expansion(self):
        """英语整篇会展开成多道小题：配额必须在**展开后**仍然成立。

        原实现先按 budget 截断行数再展开，实测 50 行变成 59 题，超出每日配额。
        """
        import json

        conn = make_conn()
        questions = [
            {"question": f"小题{i}", "question_type": "choice", "correct_answer": "A"}
            for i in range(4)
        ]
        # 3 篇英语整篇（各展开成 4 题）+ 10 道普通题
        for k in range(3):
            conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
                "analysis, difficulty, difficulty_points, knowledge_tags, source_type, "
                "review_count, ease_factor, last_interval, next_review_at, created_at, "
                "english_questions) "
                "VALUES (1, 'choice', ?, 'A', '解析', 3, '难点', '[]', 'other', 0, 2.5, 0, ?, ?, ?)",
                (f"整篇{k}", utc(-30), utc(-30), json.dumps(questions, ensure_ascii=False)),
            )
        for i in range(10):
            add_mistake(conn, f"普通题{i}", next_review_at=None, review_count=0)
        conn.commit()

        res = review_service.get_today_queue(conn, limit=99, daily_limit=9)
        self.assertEqual(len(res["items"]), 9, "展开后仍必须严格不超过每日配额")

    def test_limit_also_holds_after_expansion(self):
        """limit（单批上限）同样要在展开后生效。"""
        import json

        conn = make_conn()
        questions = [{"question": f"小题{i}", "correct_answer": "A"} for i in range(4)]
        for k in range(3):
            conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
                "analysis, difficulty, difficulty_points, knowledge_tags, source_type, "
                "review_count, ease_factor, last_interval, next_review_at, created_at, "
                "english_questions) "
                "VALUES (1, 'choice', ?, 'A', '解析', 3, '难点', '[]', 'other', 0, 2.5, 0, ?, ?, ?)",
                (f"篇{k}", utc(-30), utc(-30), json.dumps(questions, ensure_ascii=False)),
            )
        conn.commit()
        res = review_service.get_today_queue(conn, limit=5, daily_limit=0)
        self.assertEqual(len(res["items"]), 5)


if __name__ == "__main__":
    unittest.main()
