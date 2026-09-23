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

    def test_star_toggle_and_filter(self):
        mid = self._create_mistake()
        # 不带 body：切换开
        r1 = self.client.post(f"/api/mistakes/{mid}/star")
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertTrue(r1.json()["data"]["starred"])
        # 带 body：显式取消
        r2 = self.client.post(f"/api/mistakes/{mid}/star", json={"starred": False})
        self.assertEqual(r2.status_code, 200)
        self.assertFalse(r2.json()["data"]["starred"])
        # 切回开，只看收藏筛选能命中
        self.client.post(f"/api/mistakes/{mid}/star")
        r3 = self.client.get("/api/mistakes", params={"starred": True, "page": 1, "page_size": 50})
        self.assertEqual(r3.status_code, 200)
        ids = [item["id"] for item in r3.json()["data"]["items"]]
        self.assertIn(mid, ids)
        self.assertTrue(r3.json()["data"]["items"][0]["starred"])
        # 不存在：404
        r4 = self.client.post("/api/mistakes/999999/star")
        self.assertEqual(r4.status_code, 404)

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
        r = self.client.get("/api/reviews/practice", params={"mode": "real_exam", "count": 10})
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
        """未知 API 路径返回统一 JSON 结构而非 FastAPI 默认格式。

        注意：本地开发目录存在 frontend/dist 时会注册 SPA 通配路由 → 405；
        CI 没有 dist → 404。两种都应返回统一 {code,data,message}，不得有 detail。
        """
        r = self.client.post("/api/definitely-not-exist")
        self.assertIn(r.status_code, (404, 405))
        body = r.json()
        self.assertNotIn("detail", body)
        self.assertEqual(body["code"], r.status_code)

    def test_export_import_round_trip(self):
        """导出 → 导入往返：字段与图片 data URL 完整保留，**重复导入不再翻倍**。

        同时锁定列表接口瘦身契约：列表项不含英语整篇大 JSON 字段。
        """
        payload = {
            "subject_id": 3,
            "question_type": "fill",
            "question": "往返测试 $\\int_0^1 x\\,dx$",
            "correct_answer": "0.5",
            "difficulty": 2,
            "difficulty_points": "积分",
            "analysis": "$\\int_0^1 x\\,dx=0.5$",
            "knowledge_tags": ["定积分"],
            "source_type": "mock",
            "source_year": "2026",
            "source_name": "往返模拟卷",
            # 真 1x1 PNG（图片内容校验上线后，假字节会被拒；校验本身由 test_data_safety 钉）
            "images": [
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            ],
        }
        r = self.client.post("/api/mistakes", json=payload)
        self.assertEqual(r.status_code, 200)
        mid = r.json()["data"]["id"]

        exported = self.client.get("/api/export").json()["data"]
        match = [m for m in exported["mistakes"] if m["id"] == mid]
        self.assertTrue(match, "导出必须包含新建错题")
        self.assertTrue(match[0]["images"], "导出的错题应携带图片 data URL")

        r2 = self.client.post("/api/import", json={"mistakes": [match[0]]})
        self.assertEqual(r2.status_code, 200)
        data = r2.json()["data"]
        # 幂等契约：同一份导出文件重复导入，created 必须是 0 且明确指出撞了哪条
        self.assertEqual(data["created"], 0, "导出→导入往返不得把题目翻倍")
        self.assertEqual([(d["index"], d["existing_id"]) for d in data["duplicates"]], [(0, mid)])
        self.assertEqual(data["failed"], [])

        # 题干只要真的不同，就必须照常入库（去重不能变成"导入永不生效"）
        edited = dict(match[0], question=match[0]["question"] + "（变式）")
        r3 = self.client.post("/api/import", json={"mistakes": [edited]})
        self.assertEqual(r3.json()["data"]["created"], 1, "改了题干就该算新题")

        # 列表可按题干搜回，且列表项不含英语大 JSON 字段（瘦身契约）
        found = self.client.get("/api/mistakes", params={"search": "往返测试", "page": 1}).json()[
            "data"
        ]["items"]
        self.assertTrue(found)
        self.assertNotIn("english_questions", found[0])
        self.assertNotIn("english_sentences", found[0])
        for row in found:
            self.client.delete(f"/api/mistakes/{row['id']}")


class TestMocksDelete(unittest.TestCase):
    """模考成绩记错要能删（此前只有 POST/GET，错的成绩永远挂在趋势图上）。"""

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

    def test_delete_mock_then_gone(self):
        r = self.client.post(
            "/api/mocks", json={"exam_year": "2025", "total": 20, "correct": 15, "score": 75}
        )
        self.assertEqual(r.status_code, 200, r.text)
        mid = r.json()["data"]["id"]

        r = self.client.delete(f"/api/mocks/{mid}")
        self.assertEqual(r.status_code, 200, r.text)

        ids = [m["id"] for m in self.client.get("/api/mocks").json()["data"]]
        self.assertNotIn(mid, ids)

    def test_delete_missing_returns_404(self):
        r = self.client.delete("/api/mocks/999999")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
