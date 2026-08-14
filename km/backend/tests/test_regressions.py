"""复习排期、填空判题边界与来源校验的回归测试（不依赖 AI 服务）。"""

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.models.tables import TABLES_DDL
from app.services import answer_service, mistake_service, review_service


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.execute("INSERT INTO subjects (id, name) VALUES (1, '测试科目')")
    conn.commit()
    return conn


def insert_mistake(conn, question_type="choice", **kwargs) -> int:
    payload = {
        "subject_id": 1,
        "question_type": question_type,
        "question": "测试题",
        "correct_answer": "A",
        "difficulty": 3,
        "difficulty_points": "难点",
        "analysis": "解析",
        "knowledge_tags": [],
        "source_type": "other",
        **kwargs,
    }
    fields, errors = mistake_service.build_mistake_fields(payload, conn)
    assert not errors, errors
    cur = conn.execute(
        "INSERT INTO mistakes (subject_id, sub_subject_id, question_type, question, "
        "option_a, option_b, option_c, option_d, correct_answer, analysis, difficulty, "
        "knowledge_tags, approach, source, source_type, source_year, source_name, "
        "answer_aliases, difficulty_points) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["subject_id"],
            fields["sub_subject_id"],
            fields["question_type"],
            fields["question"],
            fields["option_a"],
            fields["option_b"],
            fields["option_c"],
            fields["option_d"],
            fields["correct_answer"],
            fields["analysis"],
            fields["difficulty"],
            fields["knowledge_tags_text"],
            fields["approach"],
            fields["source"],
            fields["source_type"],
            fields["source_year"],
            fields["source_name"],
            fields["answer_aliases_text"],
            fields["difficulty_points"],
        ),
    )
    conn.commit()
    return cur.lastrowid


class TestReviewSchedule(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.id = insert_mistake(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_correct_increases_mastery_and_interval(self):
        before = self.conn.execute(
            "SELECT mastery_level FROM mistakes WHERE id = ?", (self.id,)
        ).fetchone()[0]
        updated = review_service.review_mistake(self.conn, self.id, True)
        after = updated["mastery_level"]
        self.assertEqual(after, min(5, before + 1))
        interval = review_service.INTERVALS[min(after, len(review_service.INTERVALS) - 1)]
        expected = datetime.now(timezone.utc) + timedelta(days=interval)
        next_at = datetime.strptime(updated["next_review_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        self.assertLess(abs((next_at - expected).total_seconds()), 5)

    def test_wrong_resets_interval_to_one_day(self):
        updated = review_service.review_mistake(self.conn, self.id, False)
        self.assertEqual(updated["mastery_level"], 0)
        self.assertEqual(updated["wrong_count"], 1)
        expected = datetime.now(timezone.utc) + timedelta(days=1)
        next_at = datetime.strptime(updated["next_review_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        self.assertLess(abs((next_at - expected).total_seconds()), 5)
        history = review_service.get_review_history(self.conn, self.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["result"], "wrong")

    def test_fill_review_rejudges_with_user_answer(self):
        self.conn.execute(
            "UPDATE mistakes SET question_type = 'fill', correct_answer = '3.14' "
            "WHERE id = ?",
            (self.id,),
        )
        self.conn.commit()
        updated = review_service.review_mistake(
            self.conn, self.id, False, user_answer="3.140"
        )
        self.assertGreater(updated["mastery_level"], 0)
        history = review_service.get_review_history(self.conn, self.id)
        self.assertIn("你的答案", history[0]["note"])
        # 错误答案应判为 wrong：间隔重置为 1 天
        updated2 = review_service.review_mistake(
            self.conn, self.id, True, user_answer="2.00"
        )
        self.assertEqual(updated2["mastery_level"], 0)


class TestAnswerEdges(unittest.TestCase):
    def test_negative_and_scientific(self):
        self.assertTrue(answer_service.answers_match("-1", "-1"))
        self.assertTrue(answer_service.answers_match("1e-3", "0.001"))
        self.assertTrue(answer_service.answers_match("1.0004", "1", tolerance=1e-3))
        self.assertFalse(answer_service.answers_match("1.01", "1", tolerance=1e-3))

    def test_aliases_and_normalization(self):
        self.assertTrue(
            answer_service.answers_match(" ３．１４ ", "3.14", aliases=["π", "3.14"])
        )
        self.assertTrue(
            answer_service.answers_match("pi", "π", aliases=["π", "pi"])
        )

    def test_judge_fill_shape(self):
        result = answer_service.judge_fill("2", "2", aliases=["二"])
        self.assertTrue(result["correct"])
        self.assertEqual(result["normalized_user"], "2")

    def test_empty_answer_rejected(self):
        self.assertFalse(answer_service.answers_match("", "2"))


class TestSourceValidation(unittest.TestCase):
    def test_normalize_and_requirements(self):
        self.assertEqual(mistake_service.validate_source_type("self"), "other")
        self.assertEqual(mistake_service.validate_source_type("REAL_EXAM"), "real_exam")
        with self.assertRaises(ValueError):
            mistake_service.validate_source_type("unknown")
        self.assertIsNotNone(
            mistake_service.validate_source_requirements("real_exam", "", "")
        )
        self.assertIsNone(
            mistake_service.validate_source_requirements("real_exam", "2025", "")
        )
        self.assertIsNotNone(
            mistake_service.validate_source_requirements("mock", "2026", "")
        )
        self.assertIsNone(
            mistake_service.validate_source_requirements(
                "mock", "2026", "李林六套卷(一)"
            )
        )


class TestMigrationIdempotent(unittest.TestCase):
    def test_migration_sets_version_and_is_idempotent(self):
        from app import database as db

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(TABLES_DDL)
            db.migrate_database(conn)
            version1 = conn.execute(
                "SELECT value FROM app_meta WHERE key = 'migration_version'"
            ).fetchone()
            db.migrate_database(conn)
            version2 = conn.execute(
                "SELECT value FROM app_meta WHERE key = 'migration_version'"
            ).fetchone()
            self.assertEqual(version1["value"], str(db.MIGRATION_VERSION))
            self.assertEqual(version1["value"], version2["value"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
