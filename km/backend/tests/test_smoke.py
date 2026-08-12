"""核心修复的轻量回归测试：不依赖外部 AI 服务，也不触碰真实数据库。"""

import sqlite3
import unittest

from app.models.tables import TABLES_DDL
from app.services import answer_service, knowledge_service, mistake_service, review_service
from app.services.ai_service import _extract_json, _wrap_math, normalize_parsed


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.execute("INSERT INTO subjects (id, name) VALUES (1, '测试科目')")
    conn.commit()
    return conn


class TestSmoke(unittest.TestCase):
    def test_fill_numeric_tolerance(self):
        self.assertTrue(answer_service.answers_match("1.0004", "1", tolerance=1e-3))
        self.assertFalse(answer_service.answers_match("1.01", "1", tolerance=1e-3))

    def test_canonical_tags(self):
        self.assertEqual(
            knowledge_service.canonical_tags(["线性微分方程", "微分方程", "微分方程"]),
            ["微分方程"],
        )

    def test_ai_normalize_choice_does_not_default_to_a(self):
        parsed = normalize_parsed({"question_type": "choice", "correct_answer": "X"})
        self.assertEqual(parsed["correct_answer"], "")

    def test_ai_normalize_cleans_options_and_answers(self):
        parsed = normalize_parsed(
            {
                "question_type": "choice fill solution",
                "correct_answer": "答案是C",
                "option_a": "A. 1",
                "option_b": "B. 1",
                "option_c": "C. 1",
                "option_d": "D. 1",
            }
        )
        self.assertEqual(parsed["question_type"], "choice")
        self.assertEqual(parsed["correct_answer"], "C")
        self.assertEqual(parsed["option_a"], "")
        self.assertEqual(parsed["option_b"], "")

        multi = normalize_parsed(
            {"question_type": "choice", "correct_answer": "ABCD"}
        )
        self.assertEqual(multi["correct_answer"], "")

    def test_extract_json_tolerates_surrounding_text(self):
        self.assertEqual(_extract_json('前缀 {"a": 1} 后缀'), {"a": 1})

    def test_wrap_math_cleans_bad_dollars(self):
        self.assertEqual(
            _wrap_math("B$ and $$A^*$$ similar"),
            "B and $A^*$ similar",
        )
        self.assertEqual(
            _wrap_math("取 k_1$'=-$k_1,k_2$'=-$k_2 可改写"),
            "取 $k_1'=-k_1,k_2'=-k_2$ 可改写",
        )
        cleaned = _wrap_math("bad $（二重根）。\nB$ end")
        self.assertNotIn("$", cleaned)

    def test_mistake_validation_requires_points_and_analysis(self):
        conn = make_conn()
        try:
            payload = {
                "subject_id": 1,
                "question_type": "choice",
                "question": "测试题",
                "correct_answer": "A",
                "difficulty": 3,
                "difficulty_points": "",
                "analysis": "",
                "knowledge_tags": [],
                "source_type": "other",
            }
            _, errors = mistake_service.build_mistake_fields(payload, conn)
            self.assertIn("主要难点简析不能为空", errors)
            self.assertIn("解析不能为空", errors)

            payload["difficulty_points"] = "难点"
            payload["analysis"] = "解析"
            fields, errors = mistake_service.build_mistake_fields(payload, conn)
            self.assertEqual(errors, [])
            self.assertEqual(fields["knowledge_tags"], [])
        finally:
            conn.close()

    def test_list_mistakes_tag_exact_match(self):
        conn = make_conn()
        try:
            conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, difficulty, knowledge_tags) "
                "VALUES (1, 'choice', 'q1', 'A', 3, '导数')"
            )
            conn.execute(
                "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, difficulty, knowledge_tags) "
                "VALUES (1, 'choice', 'q2', 'B', 3, '导数应用')"
            )
            conn.commit()
            rows = mistake_service.list_mistakes(conn, {"tag": "导数"})
            self.assertEqual([row["question"] for row in rows], ["q1"])
        finally:
            conn.close()

    def test_practice_query_applies_limit_in_sql(self):
        conn = make_conn()
        try:
            for index in range(1, 6):
                conn.execute(
                    "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, difficulty) "
                    "VALUES (1, 'fill', ?, ?, 2)",
                    (f"q{index}", str(index)),
                )
            conn.commit()
            random_rows = review_service.get_practice_mistakes(
                conn, mode="random", count=3
            )
            curve_rows = review_service.get_practice_mistakes(
                conn, mode="curve", count=3
            )
            self.assertEqual(len(random_rows), 3)
            self.assertEqual(len(curve_rows), 3)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
