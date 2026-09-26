"""真题题目级操作：答案人工修正 + 单题转入错题本。

答案修正：choice 只收 A-D 或空、fill 收文本、solution 拒绝；
转错题：科目按关键词匹配 subjects（匹配不到就拒绝），同卷同题干幂等。
"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.database import get_connection, init_database
from app.services import exam_paper_service as eps


class QuestionOpsTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()
        self.conn = get_connection()
        cur = self.conn.execute("INSERT INTO subjects (name) VALUES ('数学')")
        self.subject_id = cur.lastrowid
        self.conn.execute(
            "INSERT INTO exam_papers (subject, year, title, source_path, answer_path, "
            "status, created_at) VALUES ('数学二', '2024', '2024 数学二真题', 'x.pdf', '', "
            "'done', 'now')"
        )
        row = self.conn.execute("SELECT id FROM exam_papers WHERE source_path = 'x.pdf'").fetchone()
        self.paper_id = row["id"]
        self.conn.execute(
            "INSERT INTO exam_questions (paper_id, no, question_type, question, option_a, "
            "option_b, option_c, option_d, correct_answer, analysis) VALUES "
            "(?, '1', 'choice', '题目一', '1', '2', '3', '4', '', ''), "
            "(?, '2', 'fill', '题目二', '', '', '', '', '', ''), "
            "(?, '3', 'solution', '题目三', '', '', '', '', '', '')",
            (self.paper_id, self.paper_id, self.paper_id),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _qid(self, no):
        return self.conn.execute(
            "SELECT id FROM exam_questions WHERE paper_id = ? AND no = ?",
            (self.paper_id, no),
        ).fetchone()["id"]


class SetAnswerTest(QuestionOpsTestBase):
    def test_choice_accepts_letter_and_rejects_other(self):
        q, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "b")
        self.assertIsNone(err)
        self.assertEqual(q["correct_answer"], "B")
        # E 是七选五的合法选项（2026-09-26 起真题库支持 A-G）；超出范围的 H 仍要拒
        q, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "E")
        self.assertIsNone(err)
        self.assertEqual(q["correct_answer"], "E")
        q, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "H")
        self.assertIsNone(q)
        self.assertIn("A 到 G", err)

    def test_choice_clears_with_empty(self):
        eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "A")
        q, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "")
        self.assertIsNone(err)
        self.assertEqual(q["correct_answer"], "")

    def test_fill_accepts_free_text(self):
        q, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("2"), "x=1")
        self.assertIsNone(err)
        self.assertEqual(q["correct_answer"], "x=1")  # fill 不做大小写归一（x=1 不是 X=1）

    def test_solution_rejected(self):
        _, err = eps.set_question_answer(self.conn, self.paper_id, self._qid("3"), "A")
        self.assertIn("解答题", err)

    def test_missing_question_404(self):
        _, err = eps.set_question_answer(self.conn, self.paper_id, 99999, "A")
        self.assertEqual(err, "题目不存在")


class ToMistakeTest(QuestionOpsTestBase):
    def test_choice_question_imports(self):
        eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "C")
        m, err = eps.question_to_mistake(self.conn, self.paper_id, self._qid("1"))
        self.assertIsNone(err)
        self.assertEqual(m["subject_id"], self.subject_id)
        self.assertEqual(m["correct_answer"], "C")
        self.assertEqual(m["source_type"], "real_exam")
        self.assertEqual(m["source_name"], "2024 数学二真题")

    def test_idempotent_same_question(self):
        eps.set_question_answer(self.conn, self.paper_id, self._qid("1"), "A")
        first, err = eps.question_to_mistake(self.conn, self.paper_id, self._qid("1"))
        self.assertIsNone(err)
        again, err = eps.question_to_mistake(self.conn, self.paper_id, self._qid("1"))
        self.assertIsNone(err)
        self.assertEqual(first["id"], again["id"])

    def test_choice_without_answer_rejected(self):
        """没答案的选择题转过去也没法复习——明确拒绝而不是静默入库。"""
        _, err = eps.question_to_mistake(self.conn, self.paper_id, self._qid("1"))
        self.assertIn("补答案", err)

    def test_missing_subject_rejected(self):
        """科目里没有对应项就拒绝，绝不静默塞进别的科目。"""
        self.conn.execute("UPDATE exam_papers SET subject = '美术' WHERE id = ?", (self.paper_id,))
        self.conn.commit()
        _, err = eps.question_to_mistake(self.conn, self.paper_id, self._qid("1"))
        self.assertIn("找不到", err)

    def test_missing_question_404(self):
        _, err = eps.question_to_mistake(self.conn, self.paper_id, 99999)
        self.assertEqual(err, "题目不存在")


if __name__ == "__main__":
    unittest.main()
