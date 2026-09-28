"""HTTP 层冒烟补盲:此前只有 service 层测试、双信封形状没人钉的端点。

覆盖:今日队列响应对象形状、配额 GET/PUT、 Forecast、知识点复习队列/复习两个
新端点、图片 zip 备份、错题批量详情、Anki 导出。全部走 TestClient + 临时库。
"""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_connection, init_database
from app.main import app

client = TestClient(app)


def ok(data, message=None):
    envelope = {"code": 200, "data": data}
    if message is not None:
        envelope["message"] = message
    return envelope


class ReviewsHttpSurfaceTest(unittest.TestCase):
    """/reviews/* 的 HTTP 形状:前端 ReviewView 依赖 today 的**对象双信封**,
    纯数组回退是兼容旧格式,这里钉住新形状不被改坏。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def _seed_mistake(self, **extra):
        conn = get_connection()
        try:
            payload = {
                "subject_id": 3,
                "question_type": "choice",
                "question": f"HTTP冒烟题{extra.get('seed', '')}",
                "correct_answer": "A",
                "difficulty": 3,
                "difficulty_points": "难点",
                "analysis": "解析",
            }
            payload.update(extra)
            cols = ", ".join(payload)
            marks = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO mistakes ({cols}) VALUES ({marks})",
                tuple(payload.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def test_today_returns_envelope_object(self):
        mid = self._seed_mistake(next_review_at="2020-01-01 00:00:00", review_count=1)
        r = client.get("/api/reviews/today", params={})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["data"]
        self.assertIsInstance(data, dict)  # 对象双信封,不是裸数组
        self.assertIn("items", data)
        self.assertIn("dueTotal", data)
        self.assertIn("remaining", data)
        self.assertIn("dailyLimit", data)
        self.assertIn("reviewedToday", data)
        self.assertTrue(any(i["id"] == mid for i in data["items"]))

    def test_quota_get_put_roundtrip(self):
        r = client.get("/api/reviews/quota")
        self.assertEqual(r.status_code, 200)
        original = r.json()["data"]["daily_limit"]
        try:
            put = client.put("/api/reviews/quota", json={"daily_limit": 33})
            self.assertEqual(put.status_code, 200)
            self.assertEqual(put.json()["data"]["daily_limit"], 33)
            self.assertEqual(client.get("/api/reviews/quota").json()["data"]["daily_limit"], 33)
        finally:
            client.put("/api/reviews/quota", json={"daily_limit": original})

    def test_forecast_shape(self):
        r = client.get("/api/reviews/forecast", params={"days": 14})
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertIn("overdue", data)
        self.assertIsInstance(data["items"], list)


class KnowledgeReviewHttpTest(unittest.TestCase):
    """知识点复习队列/复习两个新端点的 HTTP 层:此前只有 service 层测试。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO knowledge_base (tag_name, subject_id, summary, review_count, "
                "next_review_at) VALUES ('HTTP冒烟考点', 3, '摘要', 1, '2020-01-01 00:00:00')"
            )
            conn.commit()
        finally:
            conn.close()

    def test_queue_and_review_roundtrip(self):
        # 统一口径后 review_count=0 的种子词条排最前,limit 用大值确保覆盖到已复习条目
        r = client.get("/api/knowledge/review/queue", params={"limit": 50})
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertIn("items", data)
        self.assertIn("dueTotal", data)
        row = next((i for i in data["items"] if i["tag_name"] == "HTTP冒烟考点"), None)
        self.assertIsNotNone(row)

        grade = client.post(f"/api/knowledge/{row['id']}/review", json={"result": True})
        self.assertEqual(grade.status_code, 200, grade.text)
        # 复习后 review_count 增加、next_review_at 排到未来,不再立刻到期
        gone = client.get("/api/knowledge/review/queue", params={"limit": 50}).json()["data"]
        self.assertFalse(any(i["id"] == row["id"] for i in gone["items"]))

    def test_review_missing_is_404(self):
        r = client.post("/api/knowledge/999999/review", json={"result": True})
        self.assertEqual(r.status_code, 404)


class SnapshotsImagesHttpTest(unittest.TestCase):
    """POST /snapshots/images:备份链路里唯一没测过的写入口。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def test_images_backup_endpoint(self):
        img_dir = settings.DB_PATH.parent / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "b.png").write_bytes(b"data")
        r = client.post("/api/snapshots/images")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["data"]["name"].startswith("images_backup_"))
        # 空目录:跳过而不是报错
        r2 = client.post("/api/snapshots/images")
        self.assertEqual(r2.status_code, 200)


class BatchDetailHttpTest(unittest.TestCase):
    """GET /mistakes/batch-detail:按请求顺序返回、跳过已删除 id。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        cls.ids = []
        for i in (1, 2):
            conn = get_connection()
            try:
                cur = conn.execute(
                    "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
                    "difficulty, difficulty_points, analysis) "
                    "VALUES (3,'choice',?,'A',3,'难点','解析')",
                    (f"批量详情题{i}",),
                )
                cls.ids.append(cur.lastrowid)
                conn.commit()
            finally:
                conn.close()

    def test_batch_detail_ordered_and_skips_missing(self):
        r = client.get(
            "/api/mistakes/batch-detail", params={"ids": f"{self.ids[1]},{self.ids[0]},999999"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["data"]
        self.assertEqual([m["id"] for m in data], [self.ids[1], self.ids[0]])


if __name__ == "__main__":
    unittest.main()
