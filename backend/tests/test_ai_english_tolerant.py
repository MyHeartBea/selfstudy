"""英语整篇流水线的"不报废"机制（2026-09-27）。

实测翻车：录 2014 英语二完形时 DeepSeek 一次读超时，整批失败，
前面已花的提字/分析调用全部浪费。钉住两层防护：
① 提字缓存：提字成功即存 app_meta（key=图片哈希，TTL 24h），
   同批图片重试直接复用，最贵的视觉调用不重烧；
② 步骤级降级：词汇/题目清单/逐题/兜底出题失败不再抛异常报废整批，
   带伤返回 degraded=True + degraded_steps（缺了什么说清楚）。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import get_connection, init_database
from app.services import ai_english, ai_service

IMG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
OCR_TEXT = "【原文】\nThe passage is here.\n\n【题目】\n1. Q1 A) a B) b C) c D) d"

READING = {
    "is_english": True,
    "passage_translation": "译文",
    "sentences": [{"text": "The passage is here.", "translation": "原文在这里。"}],
}
VOCAB = {
    "phrases": [{"phrase": "turn out", "meaning": "结果是"}],
    "words": [{"word": "obese", "meaning": "肥胖的"}],
}
TITLE = {
    "question": "Q1",
    "option_a": "a",
    "option_b": "b",
    "option_c": "c",
    "option_d": "d",
    "correct_answer": "B",
}
QA = {
    "question": "Q1",
    "option_a": "a",
    "option_b": "b",
    "option_c": "c",
    "option_d": "d",
    "correct_answer": "B",
    "analysis": "解析",
}


def _fake_chat(vocab_error=False, titles=None, qa_error=False):
    """按 system prompt 特征路由的 _chat_json 假件（真实函数按 prompt 天然可分）。"""

    def fake(messages, **kwargs):
        system = str(messages[0]["content"])
        if "词汇助手" in system:
            if vocab_error:
                raise RuntimeError("vocab down")
            return VOCAB
        if "逐题照抄" in system:
            return {"questions": list(titles) if titles is not None else [dict(TITLE)]}
        if "与题目要求" in system:
            if qa_error:
                raise RuntimeError("qa down")
            return dict(QA)
        return dict(READING)

    return fake


class TestEnglishPipelineTolerant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def setUp(self):
        # 类级临时库全类共享，提字缓存按图片哈希写 app_meta —— 不清的话
        # 先跑的用例写完缓存，后面的用例全命中（vision 假件一次都不会被调）。
        conn = get_connection()
        try:
            conn.execute("DELETE FROM app_meta WHERE key LIKE 'english_ocr_stage_%'")
            conn.commit()
        finally:
            conn.close()

    def test_step_failure_returns_wounded_result(self):
        """词汇提取挂了：整批不报废，degraded=True + 缺项说清，题目照常出。"""
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=OCR_TEXT) as vision,
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat(vocab_error=True)),
        ):
            result = ai_english.analyze_english([IMG], "")
        self.assertTrue(result["degraded"])
        self.assertIn("生词短语提取失败", result["degraded_steps"])
        self.assertEqual(result["english_phrases"], [])
        # 单题在顶层 question 字段（english_questions 只装第 2 题起），题目链路没被词汇失败拖死
        self.assertEqual(result["english_questions"], [])
        self.assertEqual(result["question"], "Q1")
        self.assertTrue(result["analysis"])
        self.assertTrue(result["passage_text"])
        vision.assert_called_once()

    def test_fallback_question_failure_never_raises(self):
        """题目清单为空 + 兜底整篇出题也挂：返回纯精读结构（原文/翻译/句子），不抛异常。"""
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=OCR_TEXT),
            patch.object(
                ai_service, "_chat_json", side_effect=_fake_chat(titles=[], qa_error=True)
            ),
        ):
            result = ai_english.analyze_english([IMG], "")
        self.assertTrue(result["degraded"])
        self.assertIn("题目清单识别失败", result["degraded_steps"])
        self.assertIn("整篇出题失败", "".join(result["degraded_steps"]))
        self.assertEqual(result["english_questions"], [])
        self.assertEqual(result["passage_translation"], "译文")

    def test_ocr_stage_cache_skips_second_vision_call(self):
        """同批图片重试：提字只跑一次（最贵的视觉调用不再重烧）。"""
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=OCR_TEXT) as vision,
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            first = ai_english.analyze_english([IMG], "")
            second = ai_english.analyze_english([IMG], "")
        self.assertEqual(vision.call_count, 1)
        self.assertEqual(first["passage_text"], second["passage_text"])
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT value FROM app_meta WHERE key LIKE 'english_ocr_stage_%'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertIn("The passage is here", row["value"])
