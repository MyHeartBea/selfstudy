"""冲刺计划统计：日期三态（无效/已考/正常）、每日目标与周分桶、科目聚合。

口径必须与今日复习队列一致（新题 = review_count=0 AND next_review_at IS NULL）。
"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.database import get_connection, init_database
from app.services import sprint_service


class SprintTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        self._old_exam = settings.EXAM_DATE
        self._old_limit = settings.REVIEW_DAILY_LIMIT
        self.addCleanup(self._restore_settings)
        init_database()
        self.conn = get_connection()
        self.addCleanup(self.conn.close)
        # init_database 首启会播 demo 种子数据，统计是全表口径，先清掉再摆自己的棋
        self.conn.execute("DELETE FROM review_records")
        self.conn.execute("DELETE FROM mistakes")
        self.conn.commit()

    def _restore_settings(self):
        settings.EXAM_DATE = self._old_exam
        settings.REVIEW_DAILY_LIMIT = self._old_limit

    def _subject(self, name):
        cur = self.conn.execute("INSERT INTO subjects (name) VALUES (?)", (name,))
        return cur.lastrowid

    def _mistake(self, subject_id, *, due=None, never=False, paused=False):
        next_at = None
        review_count = 0
        if never:
            pass
        elif due is not None:
            next_at = due
            review_count = 2
        cur = self.conn.execute(
            "INSERT INTO mistakes (subject_id, question, difficulty, review_count, "
            "next_review_at, review_paused) VALUES (?, '题', 3, ?, ?, ?)",
            (subject_id, review_count, next_at, 1 if paused else 0),
        )
        return cur.lastrowid


class DateStatesTest(SprintTestBase):
    def test_invalid_date(self):
        settings.EXAM_DATE = "not-a-date"
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertTrue(plan["date_invalid"])
        self.assertIsNone(plan["days_left"])

    def test_empty_date(self):
        settings.EXAM_DATE = ""
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertTrue(plan["date_invalid"])

    def test_passed_date(self):
        settings.EXAM_DATE = "2020-01-01"
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertTrue(plan["passed"])

    def test_normal_date_counts(self):
        import datetime

        sid = self._subject("数学")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        future = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        for _ in range(10):
            self._mistake(sid, due=yesterday)
        for _ in range(5):
            self._mistake(sid, never=True)
        for _ in range(3):
            self._mistake(sid, due=future)
        self._mistake(sid, due=yesterday, paused=True)

        settings.EXAM_DATE = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertEqual(plan["days_left"], 10)
        self.assertEqual(plan["due_now"], 10)
        self.assertEqual(plan["never_started"], 5)
        self.assertEqual(plan["daily_target"], 2)
        self.assertEqual(len(plan["weeks"]), 2)
        self.assertEqual(plan["weeks"][0]["days"], 7)
        self.assertEqual(plan["weeks"][0]["target"], 14)
        self.assertEqual(plan["weeks"][1]["days"], 3)
        self.assertEqual(plan["weeks"][1]["target"], 6)
        self.assertEqual(plan["subjects"][0]["name"], "数学")
        self.assertEqual(plan["subjects"][0]["total"], 18)


class QuotaNoteTest(SprintTestBase):
    def test_over_quota_warns(self):
        import datetime

        sid = self._subject("数学")
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        for _ in range(100):
            self._mistake(sid, due=yesterday)
        settings.EXAM_DATE = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        settings.REVIEW_DAILY_LIMIT = 30
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertEqual(plan["daily_target"], 50)
        self.assertIn("REVIEW_DAILY_LIMIT", plan["quota_note"])

    def test_no_backlog_note(self):
        import datetime

        settings.EXAM_DATE = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertEqual(plan["daily_target"], 0)
        self.assertIn("没有积压", plan["quota_note"])


class ReviewedTodayTest(SprintTestBase):
    def test_reviewed_today_counted(self):
        import datetime

        sid = self._subject("数学")
        mid = self._mistake(sid, never=True)
        self.conn.execute(
            "INSERT INTO review_records (mistake_id, result, reviewed_at) VALUES (?, 'right', ?)",
            (mid, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        self.conn.commit()
        settings.EXAM_DATE = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        plan = sprint_service.get_sprint_plan(self.conn)
        self.assertEqual(plan["reviewed_today"], 1)


if __name__ == "__main__":
    unittest.main()
