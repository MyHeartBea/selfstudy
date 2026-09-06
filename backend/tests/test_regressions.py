"""复习排期、填空判题边界与来源校验的回归测试（不依赖 AI 服务）。"""

import sqlite3
import unittest
from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.models.tables import TABLES_DDL
from app.routers import ai as ai_router
from app.services import answer_service, mistake_service, review_service
from app.services import ai_service


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.execute("INSERT INTO subjects (id, name) VALUES (1, '测试科目')")
    conn.commit()
    return conn


def insert_mistake(conn, question_type="choice", **kwargs) -> int:
    payload = {
        "subject_id": 1,
        "question_type": question_type,
        "question": "测试题",
        "correct_answer": "A",
        "difficulty": 3,
        "difficulty_points": "难点",
        "analysis": "解析",
        "knowledge_tags": [],
        "source_type": "other",
        **kwargs,
    }
    fields, errors = mistake_service.build_mistake_fields(payload, conn)
    assert not errors, errors
    cur = conn.execute(
        "INSERT INTO mistakes (subject_id, sub_subject_id, question_type, question, "
        "option_a, option_b, option_c, option_d, correct_answer, analysis, difficulty, "
        "knowledge_tags, approach, source, source_type, source_year, source_name, "
        "answer_aliases, difficulty_points) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            fields["subject_id"],
            fields["sub_subject_id"],
            fields["question_type"],
            fields["question"],
            fields["option_a"],
            fields["option_b"],
            fields["option_c"],
            fields["option_d"],
            fields["correct_answer"],
            fields["analysis"],
            fields["difficulty"],
            fields["knowledge_tags_text"],
            fields["approach"],
            fields["source"],
            fields["source_type"],
            fields["source_year"],
            fields["source_name"],
            fields["answer_aliases_text"],
            fields["difficulty_points"],
        ),
    )
    conn.commit()
    return cur.lastrowid


class TestReviewSchedule(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.id = insert_mistake(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_correct_increases_mastery_and_interval(self):
        before = self.conn.execute(
            "SELECT mastery_level FROM mistakes WHERE id = ?", (self.id,)
        ).fetchone()[0]
        updated = review_service.review_mistake(self.conn, self.id, True)
        after = updated["mastery_level"]
        self.assertEqual(after, min(5, before + 1))
        # SM-2 简化版：首次答对（last_interval=0）安排 1 天后复习，系数 +0.1
        expected = datetime.now(timezone.utc) + timedelta(days=1)
        next_at = datetime.strptime(updated["next_review_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        self.assertLess(abs((next_at - expected).total_seconds()), 5)
        self.assertEqual(updated["last_interval"], 1)
        self.assertAlmostEqual(updated["ease_factor"], 2.6, places=6)

    def test_interval_sequence_sm2(self):
        """连续答对：间隔 1 → 3 → 8 → 22 → 62 天（上次间隔 × 难度系数自适应拉长）。"""
        intervals = []
        for _ in range(5):
            updated = review_service.review_mistake(self.conn, self.id, True)
            intervals.append(updated["last_interval"])
        self.assertEqual(intervals, [1, 3, 8, 22, 62])

    def test_wrong_penalizes_ease_and_resets_interval(self):
        # 先答对一次抬系数，再答错验证惩罚与重置
        review_service.review_mistake(self.conn, self.id, True)
        updated = review_service.review_mistake(self.conn, self.id, False)
        self.assertEqual(updated["mastery_level"], 0)
        self.assertEqual(updated["wrong_count"], 1)
        self.assertAlmostEqual(updated["ease_factor"], 2.4, places=6)  # 2.6 - 0.2
        self.assertEqual(updated["last_interval"], 1)
        expected = datetime.now(timezone.utc) + timedelta(days=1)
        next_at = datetime.strptime(updated["next_review_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        self.assertLess(abs((next_at - expected).total_seconds()), 5)
        history = review_service.get_review_history(self.conn, self.id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["result"], "wrong")

    def test_fill_review_rejudges_with_user_answer(self):
        self.conn.execute(
            "UPDATE mistakes SET question_type = 'fill', correct_answer = '3.14' "
            "WHERE id = ?",
            (self.id,),
        )
        self.conn.commit()
        updated = review_service.review_mistake(
            self.conn, self.id, False, user_answer="3.140"
        )
        self.assertGreater(updated["mastery_level"], 0)
        history = review_service.get_review_history(self.conn, self.id)
        self.assertIn("你的答案", history[0]["note"])
        # 错误答案应判为 wrong：间隔重置为 1 天
        updated2 = review_service.review_mistake(
            self.conn, self.id, True, user_answer="2.00"
        )
        self.assertEqual(updated2["mastery_level"], 0)


class TestAnswerEdges(unittest.TestCase):
    def test_negative_and_scientific(self):
        self.assertTrue(answer_service.answers_match("-1", "-1"))
        self.assertTrue(answer_service.answers_match("1e-3", "0.001"))
        self.assertTrue(answer_service.answers_match("1.0004", "1", tolerance=1e-3))
        self.assertFalse(answer_service.answers_match("1.01", "1", tolerance=1e-3))

    def test_aliases_and_normalization(self):
        self.assertTrue(
            answer_service.answers_match(" ３．１４ ", "3.14", aliases=["π", "3.14"])
        )
        self.assertTrue(
            answer_service.answers_match("pi", "π", aliases=["π", "pi"])
        )

    def test_judge_fill_shape(self):
        result = answer_service.judge_fill("2", "2", aliases=["二"])
        self.assertTrue(result["correct"])
        self.assertEqual(result["normalized_user"], "2")

    def test_empty_answer_rejected(self):
        self.assertFalse(answer_service.answers_match("", "2"))


class TestSourceValidation(unittest.TestCase):
    def test_normalize_and_requirements(self):
        self.assertEqual(mistake_service.validate_source_type("self"), "other")
        self.assertEqual(mistake_service.validate_source_type("REAL_EXAM"), "real_exam")
        with self.assertRaises(ValueError):
            mistake_service.validate_source_type("unknown")
        self.assertIsNotNone(
            mistake_service.validate_source_requirements("real_exam", "", "")
        )
        self.assertIsNone(
            mistake_service.validate_source_requirements("real_exam", "2025", "")
        )
        self.assertIsNotNone(
            mistake_service.validate_source_requirements("mock", "2026", "")
        )
        self.assertIsNone(
            mistake_service.validate_source_requirements(
                "mock", "2026", "李林六套卷(一)"
            )
        )


class TestCapturePrompt(unittest.TestCase):
    """智能录入：补充要求/参考图片/视觉通道参数是否真正进入发给模型的请求。"""

    def _capture_chat(self, fn, *args, **kwargs):
        captured = {}

        def fake_chat(messages, **kw):
            captured["messages"] = messages
            return '{"question": "q"}'

        original = ai_service._chat
        ai_service._chat = fake_chat
        try:
            fn(*args, **kwargs)
        finally:
            ai_service._chat = original
        return captured["messages"]

    def _capture_calls(self, fn, *args, **kwargs):
        """捕获每一次 _chat 调用（消息 + 关键字参数），用于断言视觉通道契约。"""
        calls = []

        def fake_chat(messages, **kw):
            calls.append((messages, kw))
            return '{"question": "q"}'

        original = ai_service._chat
        ai_service._chat = fake_chat
        try:
            fn(*args, **kwargs)
        finally:
            ai_service._chat = original
        return calls

    def test_analyze_text_includes_instruction(self):
        messages = self._capture_chat(
            ai_service.analyze_text, "题目", instruction="按配方法求解"
        )
        user = messages[1]["content"]
        self.assertIn("按配方法求解", user)
        self.assertIn("【补充要求】", user)

    def test_analyze_text_without_instruction(self):
        messages = self._capture_chat(ai_service.analyze_text, "题目")
        self.assertEqual(messages[1]["content"], "题目")

    def test_ocr_includes_instruction_and_reference_image(self):
        calls = self._capture_calls(
            ai_service.ocr_image,
            "AAAA",
            model="m",
            base_url="u",
            api_key="k",
            instruction="正交变换步骤写详细",
            reference_image_base64="BBBB",
        )
        self.assertTrue(calls)
        messages, kw = calls[0]
        content = messages[0]["content"]
        texts = [p["text"] for p in content if p["type"] == "text"]
        images = [p for p in content if p["type"] == "image_url"]
        self.assertEqual(len(images), 2)
        self.assertTrue(any("正交变换步骤写详细" in t for t in texts))
        self.assertTrue(images[1]["image_url"]["url"].startswith("data:image/png;base64,BBBB"))
        # 视觉通道参数必须真正透传（回归：重构后写死首选通道，多通道回退形同虚设）
        self.assertEqual(kw.get("model"), "m")
        self.assertEqual(kw.get("base_url"), "u")
        self.assertEqual(kw.get("api_key"), "k")

    def test_ocr_without_instruction_and_reference(self):
        calls = self._capture_calls(ai_service.ocr_image, "AAAA")
        messages, _ = calls[0]
        content = messages[0]["content"]
        images = [p for p in content if p["type"] == "image_url"]
        texts = [p["text"] for p in content if p["type"] == "text"]
        self.assertEqual(len(images), 1)
        self.assertFalse(any("【补充要求】" in t for t in texts))

    def test_ocr_default_channel_is_deepseek_vision(self):
        """未指定通道时，识图提字默认走 DeepSeek 视觉首选模型。"""
        calls = self._capture_calls(ai_service.ocr_image, "AAAA")
        _, kw = calls[0]
        self.assertEqual(kw.get("model"), ai_service.settings.AI_VISION_DS_MODEL)


class TestVisionTimeoutBudget(unittest.TestCase):
    def setUp(self):
        self.primary_model = ai_router.settings.AI_VISION_DS_MODEL
        self.primary_timeout = ai_router.settings.AI_VISION_PRIMARY_TIMEOUT
        self.fallback_timeout = ai_router.settings.AI_VISION_TIMEOUT
        ai_router.settings.AI_VISION_DS_MODEL = "deepseek-v4-flash-vision-exp"
        ai_router.settings.AI_VISION_PRIMARY_TIMEOUT = 60
        ai_router.settings.AI_VISION_TIMEOUT = 20

    def tearDown(self):
        ai_router.settings.AI_VISION_DS_MODEL = self.primary_model
        ai_router.settings.AI_VISION_PRIMARY_TIMEOUT = self.primary_timeout
        ai_router.settings.AI_VISION_TIMEOUT = self.fallback_timeout

    def test_primary_vision_model_gets_extended_timeout(self):
        self.assertEqual(
            ai_router._vision_timeout_for("deepseek-v4-flash-vision-exp", 100),
            60,
        )

    def test_fallback_vision_model_keeps_shorter_timeout(self):
        self.assertEqual(ai_router._vision_timeout_for("glm-4.6v-flash", 100), 20)

    def test_remaining_budget_caps_provider_timeout(self):
        self.assertEqual(
            ai_router._vision_timeout_for("deepseek-v4-flash-vision-exp", 12.8),
            12,
        )


class TestMigrationIdempotent(unittest.TestCase):
    def test_migration_sets_version_and_is_idempotent(self):
        from app import database as db

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(TABLES_DDL)
            db.migrate_database(conn)
            version1 = conn.execute(
                "SELECT value FROM app_meta WHERE key = 'migration_version'"
            ).fetchone()
            db.migrate_database(conn)
            version2 = conn.execute(
                "SELECT value FROM app_meta WHERE key = 'migration_version'"
            ).fetchone()
            self.assertEqual(version1["value"], str(db.MIGRATION_VERSION))
            self.assertEqual(version1["value"], version2["value"])
        finally:
            conn.close()


class TestPdfOcrFallback(unittest.TestCase):
    """真题库扫描版 PDF 的 OCR 兜底关键判定（2026-09-06 新增）。

    扫描版（图片型）PDF 无文本层，extract_text 需判定文本层是否可用，
    不足时回退到渲染成图 + 本地 Windows OCR（再退视觉）。此处只覆盖纯逻辑判定，
    不依赖真实 PDF/AI，避免测试因 OCR/视觉不可用而波动。
    """

    def test_pdf_text_usable_threshold(self):
        from app.services.exam_paper_service import _pdf_text_usable
        # 空/过少（扫描版常见）→ 不可用 → 触发 OCR 兜底
        self.assertFalse(_pdf_text_usable(""))
        self.assertFalse(_pdf_text_usable("   "))
        self.assertFalse(_pdf_text_usable("x" * 199))
        # 达到阈值 → 文本层足够，直接使用
        self.assertTrue(_pdf_text_usable("试题内容" * 120))

    def test_extract_pdf_unsupported_suffix_raises(self):
        from pathlib import Path
        from app.services.exam_paper_service import extract_text
        with self.assertRaises(ValueError):
            extract_text(Path("foo.txt"))

    def test_is_math_subject_for_vision_first(self):
        from app.services.exam_paper_service import _is_math
        # 公式密集卷 → 视觉优先（LaTeX）
        self.assertTrue(_is_math("数学二"))
        self.assertTrue(_is_math("计算机408"))
        self.assertTrue(_is_math("数学"))
        # 文科目 → 本地 OCR 优先
        self.assertFalse(_is_math("英语二"))
        self.assertFalse(_is_math("政治"))

    def test_pdf_text_usable_rejects_garbled(self):
        from app.services.exam_paper_service import _pdf_text_usable
        # 乱码（大量控制符/不可读，可读占比过低）→ 不可用 → 触发视觉/OCR 兜底
        self.assertFalse(_pdf_text_usable("\x00\x01\x02\x03" * 100))
        self.assertFalse(_pdf_text_usable("\x00" * 300 + "\x01\x02\x03" * 100))
        # 正常中文 / 英文 → 可用（走文本层，快）
        self.assertTrue(_pdf_text_usable("一、单项选择题：1～40 小题，每题 2 分。" * 30))
        self.assertTrue(_pdf_text_usable("In a linked list, a node is inserted at the head. " * 30))


if __name__ == "__main__":
    unittest.main()
