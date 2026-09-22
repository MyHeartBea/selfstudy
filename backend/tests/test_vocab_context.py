"""真题语境回链：在错题英语原文里找生词出现的位置（词边界匹配、上限、404）。"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.database import get_connection, init_database
from app.services import vocab_service


class ContextTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()
        self.conn = get_connection()
        self.addCleanup(self.conn.close)
        self.conn.execute("DELETE FROM mistakes")
        self.conn.commit()
        sid = self.conn.execute("INSERT INTO subjects (name) VALUES ('英语')").lastrowid
        self.conn.execute(
            "INSERT INTO mistakes (subject_id, question, source_name, source_year, passage_text) "
            "VALUES (?, '题', '2024 英语二真题', '2024', ?)",
            (sid, "The economic downturn has highlighted the threat to human jobs."),
        )
        self.conn.execute(
            "INSERT INTO mistakes (subject_id, question, source_name, passage_text) "
            "VALUES (?, '题', '', ?)",
            (sid, "Art schools teach students how to start a career in the arts."),
        )
        self.conn.execute(
            "INSERT INTO mistakes (subject_id, question, passage_text) VALUES (?, '题', ?)",
            (sid, "这一篇是中文原文，没有 English content。"),
        )
        self.conn.commit()
        self.conn.execute("INSERT INTO vocab_items (word, meaning) VALUES ('economic', '经济的')")
        self.conn.execute("INSERT INTO vocab_items (word, meaning) VALUES ('不存在的词', '')")
        self.conn.commit()

    def _vocab_id(self, word):
        return self.conn.execute("SELECT id FROM vocab_items WHERE word = ?", (word,)).fetchone()[
            "id"
        ]

    def _mistake_ids(self):
        return [
            r["id"] for r in self.conn.execute("SELECT id FROM mistakes ORDER BY id").fetchall()
        ]

    def test_word_boundary_match(self):
        # art 不该命中 start / career 里的子串；economic 命中第一篇
        hits = vocab_service.find_context(self.conn, self._vocab_id("economic"))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["mistake_id"], self._mistake_ids()[0])
        self.assertEqual(hits[0]["source_name"], "2024 英语二真题")
        self.assertIn("economic", hits[0]["snippet"])

    def test_substring_not_matched(self):
        self.conn.execute("INSERT INTO vocab_items (word, meaning) VALUES ('art', '艺术')")
        self.conn.commit()
        hits = vocab_service.find_context(self.conn, self._vocab_id("art"))
        # 只命中第二篇的独立词 art（第一篇没有 art 的独立出现）
        self.assertEqual([h["mistake_id"] for h in hits], [self._mistake_ids()[1]])

    def test_case_insensitive_and_empty_source_name_fallback(self):
        hits = vocab_service.find_context(self.conn, self._vocab_id("Economic"))
        self.assertEqual(len(hits), 1)

    def test_no_hit_returns_empty(self):
        self.assertEqual(vocab_service.find_context(self.conn, self._vocab_id("不存在的词")), [])

    def test_missing_vocab_returns_none(self):
        self.assertIsNone(vocab_service.find_context(self.conn, 99999))

    def test_limit_respected(self):
        sid = self.conn.execute("SELECT id FROM subjects WHERE name='英语'").fetchone()["id"]
        for _ in range(5):
            self.conn.execute(
                "INSERT INTO mistakes (subject_id, question, passage_text) VALUES (?, '题', ?)",
                (sid, "economic growth matters a lot in policy debate."),
            )
        self.conn.commit()
        hits = vocab_service.find_context(self.conn, self._vocab_id("economic"), limit=2)
        self.assertEqual(len(hits), 2)


if __name__ == "__main__":
    unittest.main()
