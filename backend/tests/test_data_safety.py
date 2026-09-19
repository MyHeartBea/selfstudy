"""第 1 批（P0 数据与可用性）回归：图片泄漏、快照降级、PUT 附加字段、批改存档、判分口径。

这些用例钉的都是**静默失败**：出错时接口照样 200、页面照样渲染，
只有数据/文件在悄悄变坏，所以必须有测试守着，不能靠手工点。
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import init_database
from app.main import app
from app.services import ai_service, answer_service, mistake_service
from fastapi.testclient import TestClient

BASE_MISTAKE = {
    "subject_id": 3,
    "question_type": "choice",
    "question": "测试题干",
    "option_a": "1",
    "option_b": "2",
    "option_c": "3",
    "option_d": "4",
    "correct_answer": "B",
    "analysis": "测试解析",
    "difficulty": 3,
    "difficulty_points": "测试难点",
}

# 1x1 PNG，够小且不触发行数/大小校验
TINY_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class _DbCase(unittest.TestCase):
    """临时库 + TestClient：每个类自己建库，不依赖别的类的生命周期。"""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmpdir.name)
        settings.DB_PATH = cls.tmp / "test.db"
        settings.BACKUP_DIR = cls.tmp / "backups"
        init_database()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def _create(self, **overrides):
        r = self.client.post("/api/mistakes", json={**BASE_MISTAKE, **overrides})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["data"]["id"]


class TestImageCleanup(_DbCase):
    """B1：删除错题必须连配图文件一起删（批量路径曾只删行）。"""

    def setUp(self):
        self.img_dir = self.tmp / "images"
        patcher = patch.object(mistake_service, "IMAGE_DIR", self.img_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _single(self):
        mid = self._create(images=[TINY_PNG])
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        name = Path(detail["images"][0]).name
        self.assertTrue((self.img_dir / name).exists())
        return mid, name

    def test_single_delete_removes_file(self):
        mid, name = self._single()
        r = self.client.delete(f"/api/mistakes/{mid}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse((self.img_dir / name).exists())

    def test_batch_delete_removes_files(self):
        mid, name = self._single()
        r = self.client.post("/api/mistakes/batch", json={"ids": [mid], "action": "delete"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["count"], 1)
        self.assertFalse(
            (self.img_dir / name).exists(),
            "批量删除只删了数据库行，配图文件会永久留在 data/images 并可被直接访问",
        )

    def test_batch_delete_reports_missing_snapshot(self):
        """B2：快照失败时不许继续宣称可回滚（文案降级 + 返回 snapshot=None）。"""
        with patch("app.routers.mistakes.snapshot_database", return_value=None):
            r = self.client.post(
                "/api/mistakes/batch", json={"ids": [self._create()], "action": "delete"}
            )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIsNone(body["data"]["snapshot"])
        self.assertIn("快照失败", body["message"])


class TestPutAttachmentKeys(_DbCase):
    """B4：PUT 不带"附加内容"键时按库里原值回填；显式提交空值才算清空。"""

    def _english(self):
        return self._create(
            question_type="solution",
            correct_answer="",
            passage_text="The passage original text.",
            passage_translation="原文译文",
            english_questions=[{"question": "Q1", "answer": "B", "wrong": False}],
            english_sentences=[{"sentence": "S1"}],
        )

    def test_omitted_keys_are_preserved(self):
        mid = self._english()
        r = self.client.put(
            f"/api/mistakes/{mid}",
            json={**BASE_MISTAKE, "question": "改过的题干"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(detail["question"], "改过的题干")
        self.assertEqual(detail["passage_text"], "The passage original text.")
        self.assertEqual(detail["passage_translation"], "原文译文")
        self.assertEqual(len(detail["english_questions"]), 1)
        self.assertEqual(len(detail["english_sentences"]), 1)

    def test_explicit_empty_clears(self):
        mid = self._english()
        r = self.client.put(
            f"/api/mistakes/{mid}",
            json={**BASE_MISTAKE, "passage_text": "", "english_questions": []},
        )
        self.assertEqual(r.status_code, 200, r.text)
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(detail["passage_text"], "")
        self.assertEqual(detail["english_questions"], [])

    def test_images_survive_partial_put(self):
        """不带 images 键的 PUT 既不该丢引用，也不该把文件删掉。"""
        img_dir = self.tmp / "put-images"
        with patch.object(mistake_service, "IMAGE_DIR", img_dir):
            mid = self._create(images=[TINY_PNG])
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        name = Path(detail["images"][0]).name
        (img_dir / name).write_bytes(b"x")
        self.client.put(f"/api/mistakes/{mid}", json=BASE_MISTAKE)
        after = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(after["images"], detail["images"])
        self.assertTrue((img_dir / name).exists())


class TestEssayPersist(_DbCase):
    """B3：AI 已经跑完的批改结果不能因为一次 INSERT 失败而丢掉。"""

    GOOD = {
        "score": 12,
        "band": "第四档",
        "dimensions": {"content": 5, "structure": 2, "language": 4, "format": 1},
        "estimated_word_count": 158,
        "corrections": [],
        "highlights": "",
        "overall": "整体不错。",
        "top_errors": [],
        "weakness_advice": "",
        "upgrade_tips": "",
        "model_version": "model",
    }

    def _grade(self):
        with patch.object(ai_service, "_chat_json", return_value=dict(self.GOOD)):
            return self.client.post(
                "/api/essays/grade", json={"kind": "e2_long", "text": "My essay."}
            )

    def test_persist_ok(self):
        r = self._grade()
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["data"]
        self.assertTrue(data["persisted"])
        self.assertIsNotNone(data["record_id"])

    def test_insert_failure_keeps_result(self):
        with patch(
            "app.routers.essay.get_connection",
            side_effect=sqlite3.OperationalError("disk locked"),
        ):
            r = self._grade()
        self.assertEqual(r.status_code, 200, "存档失败不该把已付费的批改结果一起变成 500")
        data = r.json()["data"]
        self.assertIsNone(data["record_id"])
        self.assertFalse(data["persisted"])
        self.assertEqual(data["score"], 12)
        self.assertIn("存档失败", r.json()["message"])


class TestScoringSingleSource(_DbCase):
    """F10：字母题判分口径（与前端 tests/examScoring.test.js 同一张用例表）。"""

    CASES = [
        ("aab", "AB", True),
        ("A A", "A", True),
        ("abx", "AB", True),
        ("abd", "AB", False),
        ("aabc", "abc", True),
        ("", "A", False),
        ("ex", "A", False),
    ]

    def test_judge_letters_table(self):
        for user, expected, want in self.CASES:
            self.assertEqual(
                answer_service.judge_letters(user, expected)["correct"], want, f"{user}/{expected}"
            )

    def test_judge_multi_delegates_to_letters(self):
        self.assertEqual(
            answer_service.judge_multi("BAD", "abd"), answer_service.judge_letters("BAD", "abd")
        )

    def test_server_verdict_wins_over_client_result(self):
        """前端报"答对"但字母不符时，落库记录以服务端判分为准。"""
        mid = self._create()  # correct_answer = B
        r = self.client.post(
            f"/api/mistakes/{mid}/review", json={"result": True, "user_answer": "A"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(detail["review_count"], 1)
        self.assertEqual(detail["wrong_count"], 1, "字母题的错题计数不该跟着前端的误报走")

    def test_self_mark_without_answer_is_respected(self):
        """没提交 user_answer 的自评（Q/W 键）不该被服务端覆盖。"""
        mid = self._create()
        r = self.client.post(
            f"/api/mistakes/{mid}/review", json={"result": True, "user_answer": ""}
        )
        self.assertEqual(r.status_code, 200, r.text)
        detail = self.client.get(f"/api/mistakes/{mid}").json()["data"]
        self.assertEqual(detail["wrong_count"], 0)


class TestEmptyVisionGuard(_DbCase):
    """B9：没有文字依据时不许让模型凭空编题（第二道闸）。"""

    def test_raises_without_any_text(self):
        from app.services import ai_english

        with patch.object(ai_service, "_vision_extract_text", return_value=""):
            with self.assertRaises(ai_service.AiRequestError):
                ai_english.analyze_english(["data:image/png;base64,AAAA"], "")

    def test_standard_content_raises_with_empty_images(self):
        with patch.object(ai_service, "_vision_extract_text", side_effect=RuntimeError("boom")):
            with self.assertRaises(ai_service.AiRequestError):
                ai_service._analyze_standard_content(["data:image/png;base64,AAAA"], "")


if __name__ == "__main__":
    unittest.main()
