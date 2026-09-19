"""考研倒计时端点：纯日期计算的三种分支（未来 / 日期非法 / 已考完）。"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import init_database
from app.main import app
from fastapi.testclient import TestClient


class TestExamCountdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        cls.client = TestClient(app)

    def _get(self, exam_date):
        with patch.object(settings, "EXAM_DATE", exam_date):
            r = self.client.get("/api/exam-countdown")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["data"]

    def test_future_date_counts_days(self):
        target = (date.today() + timedelta(days=10)).isoformat()
        data = self._get(target)
        self.assertEqual(data["days"], 10)
        self.assertEqual(data["date"], target)
        self.assertFalse(data["passed"])

    def test_illegal_date_returns_none_days(self):
        data = self._get("12-19")
        self.assertIsNone(data["days"])
        self.assertFalse(data["passed"])

    def test_passed_date_clamps_to_zero(self):
        data = self._get((date.today() - timedelta(days=3)).isoformat())
        self.assertEqual(data["days"], 0)
        self.assertTrue(data["passed"])


if __name__ == "__main__":
    unittest.main()
