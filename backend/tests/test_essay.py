"""英语作文批改：规整函数单测 + /api/essays 端点契约（AI 调用打桩，不联网）。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import init_database
from app.main import app
from app.services import ai_service
from app.services.ai_essay import ESSAY_KINDS, normalize_essay_grade
from fastapi.testclient import TestClient

GOOD_GRADE = {
    "score": 12,
    "band": "第四档",
    "dimensions": {"content": 5, "structure": 2, "language": 4, "format": 1},
    "estimated_word_count": 158,
    "corrections": [
        {
            "original": "He go home.",
            "corrected": "He goes home.",
            "type": "主谓一致",
            "note": "三单",
        }
    ],
    "highlights": "定语从句用得自然",
    "overall": "整体第二档上沿。",
    "top_errors": ["主谓一致", "冠词"],
    "weakness_advice": "练三单。",
    "upgrade_tips": "I think it is important -> It is widely acknowledged that...",
    "model_version": "As is vividly shown...",
}


class TestNormalizeEssayGrade(unittest.TestCase):
    def test_clamps_score_and_kind_meta(self):
        r = normalize_essay_grade({"score": 99}, "e2_long")
        self.assertEqual(r["score"], 15)
        self.assertEqual(r["max_score"], 15)
        self.assertEqual(r["kind_name"], ESSAY_KINDS["e2_long"]["name"])

    def test_band_fallback_from_score(self):
        self.assertEqual(normalize_essay_grade({"score": 12}, "e2_long")["band"], "第四档")
        self.assertEqual(normalize_essay_grade({"score": 3}, "e1_short")["band"], "第二档")
        self.assertEqual(normalize_essay_grade({"score": 0}, "e2_long")["band"], "零分档")

    def test_bad_band_text_replaced(self):
        r = normalize_essay_grade({"score": 8, "band": "优秀"}, "e2_short")
        self.assertEqual(r["band"], "第四档")  # 10 分档：7-8 为第四档

    def test_dimension_mismatch_reallocates(self):
        r = normalize_essay_grade(
            {"score": 12, "dimensions": {"content": 1, "structure": 1, "language": 1, "format": 1}},
            "e2_long",
        )
        self.assertEqual(sum(r["dimensions"].values()), 12)

    def test_dimension_sum_ok_keeps_ai_values(self):
        r = normalize_essay_grade(GOOD_GRADE, "e2_long")
        self.assertEqual(r["dimensions"]["content"], 5)
        self.assertEqual(r["corrections"][0]["type"], "主谓一致")
        self.assertEqual(len(r["highlights"]), 1)  # 字符串按行转列表
        self.assertEqual(r["top_errors"], ["主谓一致", "冠词"])

    def test_drops_correction_without_original(self):
        r = normalize_essay_grade(
            {"score": 10, "corrections": [{"corrected": "x"}, {"original": "a", "corrected": "b"}]},
            "e2_long",
        )
        self.assertEqual(len(r["corrections"]), 1)

    def test_garbage_input(self):
        r = normalize_essay_grade(None, "e2_long")
        self.assertEqual(r["score"], 0)
        self.assertEqual(r["band"], "零分档")


class TestEssayApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        # 显式建库（含 v10 的 essay_records）；不依赖别的测试类留下的生命周期
        init_database()
        cls.client = TestClient(app)

    def _grade(self, payload, parsed=None):
        with patch.object(ai_service, "_chat_json", return_value=parsed or dict(GOOD_GRADE)):
            return self.client.post("/api/essays/grade", json=payload)

    def test_grade_requires_input(self):
        r = self.client.post("/api/essays/grade", json={"kind": "e2_long"})
        self.assertEqual(r.status_code, 400)

    def test_grade_text_persists_and_lists(self):
        r = self._grade({"text": "My essay...", "kind": "e2_long", "prompt_text": "Write about X"})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["data"]
        self.assertEqual(data["score"], 12)
        self.assertEqual(data["raw_transcript"], "My essay...")
        rid = data["record_id"]
        self.assertTrue(rid)

        lst = self.client.get("/api/essays", params={"kind": "e2_long"}).json()["data"]
        self.assertEqual(lst["total"], 1)
        self.assertEqual(lst["items"][0]["id"], rid)
        self.assertIn("My essay", lst["items"][0]["excerpt"])

        # 不匹配的 kind 筛选应为空
        other = self.client.get("/api/essays", params={"kind": "e1_short"}).json()["data"]
        self.assertEqual(other["total"], 0)

    def test_grade_persist_zero_skips_record(self):
        data = self._grade({"text": "no save", "kind": "e1_short", "persist": False}).json()["data"]
        self.assertIsNone(data["record_id"])

    def test_detail_and_delete(self):
        rid = self._grade({"text": "abc", "kind": "e1_long"}).json()["data"]["record_id"]
        detail = self.client.get(f"/api/essays/{rid}").json()["data"]
        self.assertEqual(detail["essay_text"], "abc")
        self.assertEqual(detail["result"]["band"], "第四档")
        self.assertEqual(detail["max_score"], 20)

        self.assertEqual(self.client.delete(f"/api/essays/{rid}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/essays/{rid}").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/essays/{rid}").status_code, 404)

    def test_unknown_kind_falls_back(self):
        data = self._grade({"text": "x", "kind": "nonsense", "persist": False}).json()["data"]
        self.assertEqual(data["kind_name"], ESSAY_KINDS["e2_long"]["name"])


if __name__ == "__main__":
    unittest.main()
