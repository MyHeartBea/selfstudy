"""完形填空录入重构的回归（2026-10）。

实测翻车：录 2016 完形时主图=答案卡、参考图=原文，AI 把答案序列编成了一道
"题"（题干就是 "1. B 2. B 3. A…"），二级科目还错标阅读理解。重构后的约定：
- 答案表/空位/每空题干与答案 —— 本地正则解析（english_cloze），不进 AI；
- 材料里只有答案序列时直接报错，绝不让模型凭空编题；
- 完形检测结果带 sub_subject_hint=完形填空，二级科目不再错标阅读理解；
- 答案图（answer_images 角色）单独提字后本地解析成答案键。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import get_connection, init_database
from app.services import ai_english, ai_service, english_cloze
from app.services.ai_service import AiRequestError

IMG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

CLOZE_PASSAGE = (
    "Section I Use of English\n\n"
    "Happy people work differently. They're usually more __1__, and __2__ a lot. "
    "Research shows that __3__ people earn more. Some firms __4__ happiness first. "
    "In one study, __5__ workers were 12% more productive. Another found __6__ minds "
    "solve problems faster. Doctors __7__ patients recover quicker. Even sleep __8__ "
    "with mood. A positive outlook __9__ stress levels down. Laughter __10__ pain."
)

# 原文 + 答案卡（提字后 quiz 区只有答案序列 —— 2026-10 实测翻车的输入形态）
OCR_CLOZE = (
    "【原文】\n"
    + CLOZE_PASSAGE
    + "\n\n【题目】\n"
    + "\n".join(f"{i}. {l}" for i, l in enumerate("BBADCBADCA", 1))
)

READING = {
    "is_english": True,
    "passage_translation": "译文",
    "sentences": [
        {"text": "Happy people work differently.", "translation": "快乐的人工作方式不同。"}
    ],
}
VOCAB = {
    "phrases": [{"phrase": "turn out", "meaning": "结果是"}],
    "words": [{"word": "productive", "meaning": "多产的"}],
}
QA = {
    "question": "AI 改写过的题干",
    "option_a": "AI 编的选项",
    "correct_answer": "D",
    "analysis": "解析内容",
}


def _fake_chat(vocab_error=False, qa_error=False):
    """按 system prompt 特征路由的 _chat_json 假件（与 tolerant 测试同套路）。"""

    def fake(messages, **kwargs):
        system = str(messages[0]["content"])
        if "词汇助手" in system:
            if vocab_error:
                raise RuntimeError("vocab down")
            return dict(VOCAB)
        if "与题目要求" in system:
            if qa_error:
                raise RuntimeError("qa down")
            return dict(QA)
        return dict(READING)

    return fake


class TestAnswerKeyParser(unittest.TestCase):
    def test_parses_all_common_formats(self):
        self.assertEqual(english_cloze.parse_answer_key("1. B 2. B 3. A"), {1: "B", 2: "B", 3: "A"})
        self.assertEqual(english_cloze.parse_answer_key("1.B\n2、D\n3)A"), {1: "B", 2: "D", 3: "A"})
        self.assertEqual(
            english_cloze.parse_answer_key("11. A 12. B 20. b"), {11: "A", 12: "B", 20: "B"}
        )
        # 答案表页眉不干扰
        self.assertEqual(
            len(english_cloze.parse_answer_key("2016年考研英语二参考答案\n" + "1. B 2. D 3. A")), 3
        )

    def test_rejects_non_key_text(self):
        # 少于 3 对不算答案键（正文里偶然的 "2. B" 不误判）
        self.assertEqual(english_cloze.parse_answer_key("Chapter 2. Birds fly. 3. A few more."), {})
        # 字母后紧跟字母的不能吃走（1. Bad 不是 1.B）
        self.assertEqual(english_cloze.parse_answer_key("1. Bad 2. Good 3. Ugly"), {})
        # 数字属于更长的年份时不拆出两位（2016. B 吃不出 16. B）
        self.assertNotIn(
            16, english_cloze.parse_answer_key("In 2016. B was the answer. 2. D 3. A 4. C")
        )

    def test_looks_like_answer_key(self):
        key = "\n".join(f"{i}. {l}" for i, l in enumerate("BBADCBADCA", 1))
        self.assertTrue(english_cloze.looks_like_answer_key(key))
        self.assertTrue(english_cloze.looks_like_answer_key("2016年英语二答案\n" + key))
        self.assertFalse(english_cloze.looks_like_answer_key(CLOZE_PASSAGE + "\n" + key))
        self.assertFalse(english_cloze.looks_like_answer_key("1. B 2. D"))

    def test_is_answer_sequence_text(self):
        self.assertTrue(english_cloze.is_answer_sequence_text("1. B 2. B 3. A 4. D 5. C 6. B"))
        self.assertFalse(english_cloze.is_answer_sequence_text("The major reason is ____."))


class TestClozeDetection(unittest.TestCase):
    def test_title_marker(self):
        self.assertTrue(english_cloze.detect_cloze("Section I Use of English\n\nSome text."))

    def test_numbered_blanks(self):
        self.assertTrue(english_cloze.detect_cloze(CLOZE_PASSAGE))

    def test_gapped_five_is_not_cloze(self):
        # 七选五只有 5 个空，必须留在原 AI 拆题管线
        passage = "A. B. C. D. E. " + " ".join(f"__{i}__" for i in range(41, 46))
        self.assertFalse(english_cloze.detect_cloze(passage))

    def test_plain_blanks_fallback(self):
        passage = " ".join(["He said ____ and left."] * 12)
        self.assertTrue(english_cloze.detect_cloze(passage))

    def test_reading_passage_rejected(self):
        self.assertFalse(
            english_cloze.detect_cloze("Text 2\nBiologists estimate that birds fly south in 2016.")
        )


class TestBlankParsing(unittest.TestCase):
    def test_all_marker_forms(self):
        text = "a __1__ b\n(2)____ c\n____(3) d\n4____ e\n____5 f"
        nos = [b["no"] for b in english_cloze.find_numbered_blanks(text)]
        self.assertEqual(nos, [1, 2, 3, 4, 5])

    def test_year_not_eaten(self):
        text = "In 2016 ____ began. " + " ".join(f"__{i}__" for i in range(1, 9))
        nos = [b["no"] for b in english_cloze.find_numbered_blanks(text)]
        self.assertEqual(nos, [1, 2, 3, 4, 5, 6, 7, 8])

    def test_too_few_numbers_rejected(self):
        self.assertEqual(english_cloze.find_numbered_blanks("only __1__ and __2__ here"), [])


class TestBuildQuestions(unittest.TestCase):
    def test_per_blank_question_with_answers(self):
        key = {i: l for i, l in enumerate("BBADCBADCA", 1)}
        qs = english_cloze.build_cloze_questions(CLOZE_PASSAGE, key)
        self.assertEqual(len(qs), 10)
        self.assertIn("____", qs[0]["question"])
        self.assertNotIn("__1__", qs[0]["question"])  # 目标空已替换
        self.assertIn("__2__", qs[0]["question"])  # 同句其它空保留编号
        self.assertEqual(qs[0]["correct_answer"], "B")
        self.assertEqual(qs[9]["correct_answer"], "A")
        self.assertEqual(qs[0]["question_type"], "choice")

    def test_sequential_numbering_without_marks(self):
        passage = " ".join(["He said ____ and left."] * 12)
        qs = english_cloze.build_cloze_questions(passage, {1: "A", 2: "B"})
        self.assertEqual(len(qs), 12)
        self.assertEqual(qs[0]["correct_answer"], "A")
        self.assertEqual(qs[2]["correct_answer"], "")

    def test_options_parsed_and_attached(self):
        quiz = (
            "1. [A] happy [B] sad [C] angry [D] calm\n"
            "2. [A] work [B] rest [C] play [D] sleep\n"
            "3. [A] fast [B] slow [C] hard [D] soft"
        )
        opts = english_cloze.parse_cloze_options(quiz)
        self.assertEqual(opts[1], {"A": "happy", "B": "sad", "C": "angry", "D": "calm"})
        key = {1: "A", 2: "D", 3: "B"}
        passage = "He is __1__ at home. She needs __2__ well. It runs __3__ now."
        qs = english_cloze.attach_options(english_cloze.build_cloze_questions(passage, key), opts)
        self.assertEqual(qs[0]["option_a"], "happy")
        self.assertEqual(qs[1]["option_d"], "sleep")


class TestEnglishPipelineCloze(unittest.TestCase):
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
        # 类级临时库共享，提字缓存不清会让 vision 假件一次都不被调
        conn = get_connection()
        try:
            conn.execute("DELETE FROM app_meta WHERE key LIKE 'english_ocr_stage_%'")
            conn.commit()
        finally:
            conn.close()

    def test_cloze_built_locally_with_answers(self):
        """原文+答案卡 → 每空一题、答案对齐、二级科目提示=完形填空。"""
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=OCR_CLOZE),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            result = ai_english.analyze_english([IMG], "")
        self.assertTrue(result["is_english"])
        self.assertEqual(result["sub_subject_hint"], "完形填空")
        # 顶层=第 1 空，其余 9 空进 english_questions；题干来自本地拆题（AI 的"改写题干"不采信）
        self.assertIn("____", result["question"])
        self.assertNotIn("AI 改写", result["question"])
        self.assertEqual(result["correct_answer"], "B")
        self.assertEqual(len(result["english_questions"]), 9)
        self.assertEqual(result["english_questions"][0]["correct_answer"], "B")
        self.assertEqual(result["english_questions"][8]["correct_answer"], "A")
        # 原文空位标记保留（前端点击跳题依赖它）
        self.assertIn("__2__", result["passage_text"])
        # 全链无缺料 → 不降级
        self.assertIsNone(result.get("degraded"))
        self.assertEqual(result["passage_translation"], "译文")

    def test_answer_images_role_extracted_separately(self):
        """答案图（answers 角色）单独提字：本地解析成答案键，选项从题目区解析。"""
        ocr_with_options = (
            "【原文】\n" + CLOZE_PASSAGE + "\n\n【题目】\n1. [A] down [B] up [C] out [D] off"
        )
        answer_text = "\n".join(f"{i}. {l}" for i, l in enumerate("ABBADCBADCA", 1))

        def fake_vision(images, instruction="", *args, **kwargs):
            if "答案表" in (instruction or ""):
                return answer_text
            return ocr_with_options

        with (
            patch.object(ai_english, "_vision_extract_text", side_effect=fake_vision),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            result = ai_english.analyze_english([IMG], "", answer_images=[IMG])
        self.assertEqual(result["correct_answer"], "A")
        self.assertEqual(result["option_a"], "down")
        self.assertEqual(result["english_questions"][0]["correct_answer"], "B")

    def test_answer_image_failure_degrades_not_raises(self):
        """答案图提字失败：答案留空并明说，整批不报废。"""
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=OCR_CLOZE),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            # 正常路径先跑一次（答案键来自 quiz 区），不影响本用例
            result = ai_english.analyze_english([IMG], "")
        self.assertTrue(result["is_english"])

        conn = get_connection()
        try:
            conn.execute("DELETE FROM app_meta WHERE key LIKE 'english_ocr_stage_%'")
            conn.commit()
        finally:
            conn.close()

        def broken_vision(images, instruction="", *args, **kwargs):
            if "答案表" in (instruction or ""):
                raise RuntimeError("vision down")
            return OCR_CLOZE

        with (
            patch.object(ai_english, "_vision_extract_text", side_effect=broken_vision),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            result2 = ai_english.analyze_english([IMG], "", answer_images=[IMG])
        # quiz 区答案键兜底生效，答案不丢
        self.assertEqual(result2["correct_answer"], "B")
        self.assertIsNone(result2.get("degraded"))

    def test_answer_key_only_material_raises(self):
        """材料里只有答案序列：直接报错，绝不让模型把答案编成题。"""
        with self.assertRaises(AiRequestError) as ctx:
            ai_english.analyze_english([], "1. B 2. B 3. A 4. D 5. C 6. B 7. A")
        self.assertIn("只识别到答案序列", str(ctx.exception))

    def test_answers_before_passage_get_swapped(self):
        """提字把答案表排在原文前面且漏打小标题：自动换位，完形照常拆题。"""
        swapped = (
            "\n".join(f"{i}. {l}" for i, l in enumerate("BBADCBADCA", 1))
            + "\n【原文】\n"
            + CLOZE_PASSAGE
        )
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=swapped),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            result = ai_english.analyze_english([IMG], "")
        self.assertEqual(result["sub_subject_hint"], "完形填空")
        self.assertEqual(len(result["english_questions"]), 9)

    def test_reading_with_answer_sheet_keeps_passage_without_fake_question(self):
        """普通阅读 + 答案卡（题目页缺失）：题干留空、明说缺料，不出伪题。"""
        ocr = "【原文】\nText 1\nMany people talked of the new jobs the department reported.\n\n【题目】\n1. B 2. B 3. A 4. D 5. C"
        with (
            patch.object(ai_english, "_vision_extract_text", return_value=ocr),
            patch.object(ai_service, "_chat_json", side_effect=_fake_chat()),
        ):
            result = ai_english.analyze_english([IMG], "")
        self.assertTrue(result["is_english"])
        self.assertTrue(result["degraded"])
        self.assertTrue(any("只识别到答案序列" in s for s in result["degraded_steps"]))
        self.assertEqual(result["question"], "")
        self.assertEqual(result["english_questions"], [])


class TestSubSubjectHint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def test_normalize_preserves_hint(self):
        base = ai_english.normalize_english_parsed(
            {"is_english": True, "sub_subject_hint": "完形填空"}, ""
        )
        self.assertEqual(base["sub_subject_hint"], "完形填空")
        base2 = ai_english.normalize_english_parsed({"is_english": True}, "")
        self.assertEqual(base2["sub_subject_hint"], "")

    def test_router_maps_cloze_sub_subject(self):
        """完形提示 → 英语二/完形填空；无提示维持缺省阅读理解。"""
        from app.routers.ai import _auto_subject_ids

        conn = get_connection()
        try:
            sid, sub = _auto_subject_ids(conn, "英语")
            self.assertEqual((sid, sub), (2, 8))  # 阅读理解（缺省不变）
            sid, sub = _auto_subject_ids(conn, "英语", "完形填空")
            self.assertEqual((sid, sub), (2, 7))  # 完形填空
            # 未知的 sub_hint 回退缺省，不许返回空
            sid, sub = _auto_subject_ids(conn, "英语", "不存在的子科目")
            self.assertEqual((sid, sub), (2, 8))
        finally:
            conn.close()
