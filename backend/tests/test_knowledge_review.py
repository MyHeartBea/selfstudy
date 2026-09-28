"""知识点 SM-2 复习队列回归：队列表迁移、新条目优先轮转、记住/忘了的调度口径。

口径必须与错题的今日队列一致（新条目优先 + last_reviewed 轮转），
调度参数与 review_service._next_schedule 同源 —— 两边漂移就是两套记忆曲线。
"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.database import get_connection, init_database
from app.services import knowledge_service


class TestKnowledgeReviewQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def _create(self, tag, subject_id=None):
        item, errors = knowledge_service.create_knowledge(
            self.conn, {"tag_name": tag, "subject_id": subject_id, "summary": f"{tag} 的摘要"}
        )
        self.assertEqual(errors, [])
        return item

    def setUp(self):
        self.conn = get_connection()

    def tearDown(self):
        self.conn.close()

    def test_new_columns_exist_and_new_items_lead_queue(self):
        """迁移补列成功；从未复习的词条按新条目排在队列最前。"""
        row = self.conn.execute("PRAGMA table_info(knowledge_base)").fetchall()
        cols = {r["name"] for r in row}
        self.assertTrue(
            {"ease_factor", "last_interval", "review_count", "last_reviewed_at", "next_review_at"}
            <= cols
        )
        self._create("中值定理")
        self._create("洛必达法则")
        self.conn.commit()
        queue = knowledge_service.get_knowledge_review_queue(self.conn)
        names = [item["tag_name"] for item in queue["items"]]
        self.assertIn("中值定理", names)
        self.assertIn("洛必达法则", names)
        self.assertGreaterEqual(queue["dueTotal"], 2)

    def test_review_correct_schedules_sm2(self):
        """记住：首次间隔 1 天、系数上探；再次记住间隔 = 1 × 2.6 ≈ 3 天。"""
        item = self._create("泰勒公式")
        first = knowledge_service.review_knowledge(self.conn, item["id"], True)
        self.assertEqual(first["last_interval"], 1)
        self.assertEqual(first["review_count"], 1)
        self.assertAlmostEqual(first["ease_factor"], 2.6)
        self.assertIsNotNone(first["next_review_at"])
        self.assertIsNotNone(first["last_reviewed_at"])
        second = knowledge_service.review_knowledge(self.conn, item["id"], True)
        self.assertEqual(second["last_interval"], 3)
        self.assertAlmostEqual(second["ease_factor"], 2.7)

    def test_review_wrong_resets_interval(self):
        """忘了：间隔重置 1 天、系数下降；复习后短期不再出现在队列。"""
        item = self._create("拐点判定")
        first = knowledge_service.review_knowledge(self.conn, item["id"], True)
        second = knowledge_service.review_knowledge(self.conn, item["id"], False)
        self.assertEqual(second["last_interval"], 1)
        self.assertLess(second["ease_factor"], first["ease_factor"])
        queue = knowledge_service.get_knowledge_review_queue(self.conn)
        self.assertNotIn("拐点判定", [i["tag_name"] for i in queue["items"]])

    def test_review_missing_returns_none(self):
        self.assertIsNone(knowledge_service.review_knowledge(self.conn, 999999, True))


if __name__ == "__main__":
    unittest.main()
