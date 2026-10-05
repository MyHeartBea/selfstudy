"""B7 生词积压消化策略：到期队列按真题年份优先（近年 → 其它年份 → 无年份）。

每日定量（配额）在 855b323 已落地；本文件钉的是排序口径：
- 年份从 vocab_items.source 文本提取（如「2023 英语二 Text1」）
- 近年窗口 = 考试日年份的前 5 年（考 2026 → 2021-2025）
- 组内低掌握度先、最久未刷先；整表洗牌后稳定排序，键相同保留随机序
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from app.config import settings
from app.database import get_connection, init_database
from app.services import vocab_service


class DuePriorityTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()
        self.conn = get_connection()
        self.addCleanup(self.conn.close)
        self.conn.execute("DELETE FROM vocab_items")
        self.conn.commit()
        # 四档：近年真题 / 老年份 / 无年份 / 近年但掌握度高
        self.conn.executemany(
            "INSERT INTO vocab_items (word, meaning, source, mastery_level) VALUES (?, '', ?, ?)",
            [
                ("recent_word", "2023 英语二 Text1", 0),
                ("old_word", "2014 英语一 Text3", 0),
                ("noyear_word", "", 0),
                ("recent_high", "2025 英语二 Text2", 6),
            ],
        )
        self.conn.commit()

    def _due_words(self, limit=None):
        if limit is None:
            return [row["word"] for row in vocab_service.get_due_vocab(self.conn)]
        return [row["word"] for row in vocab_service.get_due_vocab(self.conn, limit=limit)]

    def test_recent_year_first(self):
        words = self._due_words()
        self.assertEqual(words.index("recent_word"), 0)

    def test_bucket_order(self):
        words = self._due_words()
        self.assertLess(words.index("recent_word"), words.index("old_word"))
        self.assertLess(words.index("old_word"), words.index("noyear_word"))
        # 年份档压过掌握度：近年高掌握度词不插队到低掌握度前面
        self.assertLess(words.index("recent_word"), words.index("recent_high"))

    def test_mastery_tiebreak_within_bucket(self):
        self.conn.execute(
            "INSERT INTO vocab_items (word, meaning, source, mastery_level) VALUES (?, '', ?, ?)",
            ("recent_low", "2024 英语二 Text1", 2),
        )
        self.conn.commit()
        words = self._due_words()
        self.assertLess(words.index("recent_low"), words.index("recent_high"))

    def test_limit_truncates(self):
        words = self._due_words(limit=2)
        self.assertEqual(len(words), 2)
        # 截断后留下的必须仍来自最高年份档
        self.assertIn("recent_word", words)
        self.assertNotIn("noyear_word", words)

    def test_order_stable_under_shuffle(self):
        # 多次调用：年份档顺序必须永远成立（洗牌只影响键相同的条目）
        for _ in range(5):
            words = self._due_words()
            self.assertLess(words.index("recent_word"), words.index("noyear_word"))

    def test_recent_exam_years_from_exam_date(self):
        with mock.patch.object(settings, "EXAM_DATE", "2026-12-19"):
            self.assertEqual(vocab_service.recent_exam_years(), {2021, 2022, 2023, 2024, 2025})

    def test_recent_exam_years_bad_date_falls_back(self):
        # 考试日非法 → 用当前年份；把 now 钉到 2030 才能与真实 EXAM_DATE 区分
        fake = mock.MagicMock(wraps=datetime)
        fake.now.return_value = datetime(2030, 6, 1)
        with (
            mock.patch.object(settings, "EXAM_DATE", "not-a-date"),
            mock.patch.object(vocab_service, "datetime", fake),
        ):
            self.assertEqual(vocab_service.recent_exam_years(), {2025, 2026, 2027, 2028, 2029})


if __name__ == "__main__":
    unittest.main()
