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

    def test_list_search_matches_prompt_and_essay_and_escapes_wildcards(self):
        """/api/essays?search= 是命令面板全站搜索跳回档案页用的。"""
        self._grade(
            {"text": "The algorithm matters.", "kind": "e2_long", "prompt_text": "谈谈算法"}
        )
        hit = self.client.get("/api/essays", params={"search": "算法"}).json()["data"]
        self.assertEqual(hit["total"], 1)
        self.assertIn("算法", hit["items"][0]["excerpt"] + "谈谈算法")
        # 命中正文也算
        self.assertEqual(
            self.client.get("/api/essays", params={"search": "matters"}).json()["data"]["total"], 1
        )
        self.assertEqual(
            self.client.get("/api/essays", params={"search": "zzz-无"}).json()["data"]["total"], 0
        )
        # `%` 必须是字面量：不转义的话任何一条含"5"的记录都会被"50%"命中
        self.assertEqual(
            self.client.get("/api/essays", params={"search": "%"}).json()["data"]["total"], 0
        )

    def test_list_pagination_uses_page_size(self):
        """分页参数全站统一为 page_size（essay 曾用 per_page，是唯一的例外名）。"""
        base = self.client.get("/api/essays", params={"kind": "e2_long"}).json()["data"]["total"]
        for i in range(3):
            self._grade({"text": f"essay {i}", "kind": "e2_long"})

        page2 = self.client.get(
            "/api/essays", params={"kind": "e2_long", "page": 2, "page_size": 2}
        ).json()["data"]
        total = base + 3
        self.assertEqual(page2["total"], total)
        # 断言与"库里原本有几条"无关：只按总数算第 2 页（每页 2 条）应有几条
        self.assertEqual(len(page2["items"]), max(0, min(2, total - 2)))

        last = self.client.get(
            "/api/essays", params={"kind": "e2_long", "page": total, "page_size": 1}
        ).json()["data"]
        self.assertEqual(len(last["items"]), 1)
        overflow = self.client.get(
            "/api/essays", params={"kind": "e2_long", "page": total + 1, "page_size": 1}
        ).json()["data"]
        self.assertEqual(overflow["items"], [])

        # 旧名字必须**彻底失效**（FastAPI 忽略未声明的 query → 回落到默认 15 条），
        # 否则等于两套参数名并存，前端漏改也发现不了。
        legacy = self.client.get("/api/essays", params={"kind": "e2_long", "per_page": 1}).json()[
            "data"
        ]
        self.assertEqual(len(legacy["items"]), base + 3)

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
