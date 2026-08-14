"""接口层冒烟测试：临时数据库 + TestClient，验证关键端点与契约。"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.main import app
from fastapi.testclient import TestClient


class TestApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        cls._client_ctx = TestClient(app)
        cls._client_ctx.__enter__()
        cls.client = cls._client_ctx

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)
        cls._tmpdir.cleanup()

    def _create_mistake(self, **overrides):
        payload = {
            "subject_id": 3,
            "question_type": "choice",
            "question": "接口测试题 $x^2$",
            "option_a": "1",
            "option_b": "2",
            "option_c": "3",
            "option_d": "4",
            "correct_answer": "B",
            "difficulty": 3,
            "difficulty_points": "测试难点",
            "analysis": "测试解析",
            "knowledge_tags": ["导数"],
            "source_type": "real_exam",
            "source_year": "2025",
            **overrides,
        }
        r = self.client.post("/api/mistakes", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["data"]["id"]

    def test_base_data(self):
        r = self.client.get("/api/subjects")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()["data"]), 4)
        r2 = self.client.get("/api/sub_subjects", params={"subject_id": 3})
        self.assertEqual(r2.status_code, 200)
        self.assertGreaterEqual(len(r2.json()["data"]), 2)

    def test_mistake_crud_and_multi_difficulty_filter(self):
        mid = self._create_mistake()
        r2 = self.client.get(
            "/api/mistakes",
            params=[
                ("difficulty", 3),
                ("difficulty", 4),
                ("page", 1),
                ("page_size", 50),
            ],
        )
        self.assertEqual(r2.status_code, 200)
        ids = [item["id"] for item in r2.json()["data"]["items"]]
        self.assertIn(mid, ids)

        r3 = self.client.get(f"/api/mistakes/{mid}")
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["data"]["knowledge_tags"], ["导数"])

        r4 = self.client.post(f"/api/mistakes/{mid}/review", json={"result": True})
        self.assertEqual(r4.status_code, 200, r4.text)

        r5 = self.client.delete(f"/api/mistakes/{mid}")
        self.assertEqual(r5.status_code, 200)

    def test_real_exam_practice_mode(self):
        self._create_mistake()
        r = self.client.get(
            "/api/reviews/practice", params={"mode": "real_exam", "count": 10}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertTrue(data)
        self.assertTrue(all(item["source_type"] == "real_exam" for item in data))

    def test_judge_fill_endpoint(self):
        mid = self._create_mistake(
            question_type="fill",
            correct_answer="2",
            answer_aliases=["二"],
            source_type="other",
        )
        r = self.client.post(f"/api/mistakes/{mid}/judge", json={"user_answer": "二"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["correct"])
        self.client.delete(f"/api/mistakes/{mid}")

    def test_export_includes_master_data(self):
        r = self.client.get("/api/export")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertIn("subjects", data)
        self.assertIn("sub_subjects", data)
        self.assertIn("mistakes", data)
        self.assertIn("knowledge", data)

    def test_validation_error_shape(self):
        r = self.client.post("/api/mistakes", json={})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["code"], 422)

    def test_source_type_validation(self):
        mid = self._create_mistake()
        r = self.client.post(
            f"/api/mistakes/{mid}/source-type",
            json={"source_type": "real_exam"},
        )
        self.assertEqual(r.status_code, 400)  # 真题必须填年份
        r2 = self.client.post(
            f"/api/mistakes/{mid}/source-type",
            json={"source_type": "real_exam", "source_year": "2025"},
        )
        self.assertEqual(r2.status_code, 200)
        self.client.delete(f"/api/mistakes/{mid}")

    def test_stats_and_knowledge_endpoints(self):
        r = self.client.get("/api/stats")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_mistakes", r.json()["data"])
        r2 = self.client.get("/api/reviews/stats")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("due_today", r2.json()["data"])
        r3 = self.client.get("/api/knowledge", params={"page": 1, "page_size": 5})
        self.assertEqual(r3.status_code, 200)
        self.assertIn("items", r3.json()["data"])

    def test_knowledge_patch_semantics(self):
        """PATCH 空 body 不清空摘要；单字段更新生效。"""
        mid = self._create_mistake(knowledge_tags=["导数"])
        rows = self.client.get(
            "/api/knowledge", params={"tag": "导数", "page": 1, "page_size": 10}
        ).json()["data"]["items"]
        kid = rows[0]["id"]
        summary_before = rows[0]["summary"]
        r = self.client.patch(f"/api/knowledge/{kid}", json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["summary"], summary_before)
        r2 = self.client.patch(f"/api/knowledge/{kid}", json={"summary": "新的摘要"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["data"]["summary"], "新的摘要")
        self.client.patch(f"/api/knowledge/{kid}", json={"summary": summary_before})
        self.client.delete(f"/api/mistakes/{mid}")

    def test_pagination_page_without_page_size(self):
        """只传 page 不传 page_size 应正常返回（不再 500）。"""
        r = self.client.get("/api/mistakes", params={"page": 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["page_size"], 20)

    def test_unknown_api_returns_uniform_json(self):
        """未知 API 路径返回统一 JSON 结构而非 FastAPI 默认格式。"""
        r = self.client.post("/api/definitely-not-exist")
        self.assertEqual(r.status_code, 405)
        body = r.json()
        self.assertNotIn("detail", body)
        self.assertEqual(body["code"], 405)


if __name__ == "__main__":
    unittest.main()
