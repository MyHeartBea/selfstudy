"""实体列表端点的 LIKE 转义：全站口径是 `search_service.like_pattern` + `ESCAPE '\\'`。

`/api/search` 的转义由 test_search.py 钉住；这里钉的是各实体**自己的**搜索/筛选入口——
它们曾各自手写 `f"%{q}%"`，搜 `50%` 会命中一切含 5 的内容（AGENTS 第 3 节点名的静默错数据）。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import get_connection, init_database
from app.main import app
from fastapi.testclient import TestClient


def _seed(conn):
    conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, analysis) "
        "VALUES (3,'choice','已知增长率 50% 求末值','等比数列')"
    )
    conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, analysis) "
        "VALUES (3,'choice','已知增长率 5 倍求末值','指数增长')"
    )
    conn.execute(
        "INSERT INTO knowledge_base (tag_name, subject_id, summary) "
        "VALUES ('正确率50%',3,'错题占比过半的考点')"
    )
    conn.execute(
        "INSERT INTO knowledge_base (tag_name, subject_id, summary) "
        "VALUES ('正确率5成',3,'相近但不同的考点')"
    )
    conn.execute(
        "INSERT INTO formula_items (category, title, content) "
        "VALUES ('高等数学','增量公式50%版','a*(1+0.5)')"
    )
    conn.execute(
        "INSERT INTO formula_items (category, title, content) "
        "VALUES ('高等数学','增量公式5倍版','a*5')"
    )
    conn.execute(
        "INSERT INTO vocab_items (word, meaning, kind) VALUES ('ratio50','占比 50% 的指标','word')"
    )
    conn.execute(
        "INSERT INTO vocab_items (word, meaning, kind) VALUES ('ratio5','占比 5 倍的指标','word')"
    )
    conn.commit()


class LikeEscapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        conn = get_connection()
        _seed(conn)
        conn.close()
        cls.client = TestClient(app)

    def _get_items(self, url, params):
        r = self.client.get(url, params=params)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["code"], 200)
        data = body["data"]
        # 各实体不传 page 时都是裸数组约定；practice 恒为数组
        self.assertIsInstance(data, list, f"{url} 应返回裸数组")
        return data

    def test_mistake_search_escapes_percent(self):
        items = self._get_items("/api/mistakes", {"search": "50%"})
        self.assertEqual(len(items), 1)
        self.assertIn("50%", items[0]["question"])

    def test_mistake_approach_filter_escapes(self):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE mistakes SET approach='正确率 50% 场景' WHERE question LIKE '%增长率 5 倍%'"
            )
            conn.commit()
        finally:
            conn.close()
        items = self._get_items("/api/mistakes", {"approach": "50%"})
        self.assertEqual(len(items), 1)
        self.assertIn("50%", items[0]["approach"])

    def test_knowledge_tag_filter_escapes(self):
        items = self._get_items("/api/knowledge", {"tag": "正确率50%"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tag_name"], "正确率50%")

    def test_formula_search_escapes(self):
        items = self._get_items("/api/formulas", {"search": "50%"})
        self.assertEqual(len(items), 1)
        self.assertIn("50%", items[0]["title"])

    def test_vocab_search_escapes(self):
        items = self._get_items("/api/vocab", {"search": "50%"})
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["word"], "ratio50")

    def test_practice_search_escapes(self):
        items = self._get_items("/api/reviews/practice", {"search": "50%"})
        self.assertEqual(len(items), 1)
        self.assertIn("50%", items[0]["question"])


class HealthRedactionTest(unittest.TestCase):
    """未配置 token 时 /health 全网可读，环境信息（Python 版本/监听地址）必须裁掉。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        cls.client = TestClient(app)

    def test_no_token_hides_environment_fields(self):
        with patch.object(settings, "API_TOKEN", ""):
            r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertEqual(data["status"], "ok")
        self.assertNotIn("python", data)
        self.assertNotIn("host", data)

    def test_with_token_environment_fields_returned(self):
        with patch.object(settings, "API_TOKEN", "secret-token"):
            r = self.client.get("/api/health", headers={"X-API-Token": "secret-token"})
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertIn("python", data)
        self.assertIn("host", data)

    def test_with_token_missing_token_is_401(self):
        with patch.object(settings, "API_TOKEN", "secret-token"):
            r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
