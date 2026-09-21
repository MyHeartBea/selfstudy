"""推理模型（deepseek-flash）预算与截断重试的回归。

背景：`deepseek-flash` 会先输出 reasoning_content 再输出正文。若 max_tokens 只按
"正文长度"估算，预算会被推理吃光 → `finish_reason=length`、content 为空**或被静默截断**。
实测过的两个真实故障：
- 拆题调用 12000 预算里 11998 是 reasoning_tokens、正文 0 字 → 整份试卷导入失败；
- 识图提字 max_tokens 写死 4000 → 英语原文只识出一两段、题目与原文错位。

设计：余量与"截断就翻倍重试"统一收敛在 `_chat`，所有调用方（含识图）自动受益。
"""

import json
import unittest
from unittest.mock import patch

from app.services import ai_service


def _resp(content, finish_reason="stop", reasoning=0):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"completion_tokens_details": {"reasoning_tokens": reasoning}},
    }


class BudgetHeadroomTest(unittest.TestCase):
    def _capture_payload(self, **chat_kwargs):
        seen = {}

        def fake_post(opener, request, timeout):
            seen["payload"] = json.loads(request.data.decode())
            return _resp("ok")

        with (
            patch.object(ai_service, "_post_chat", side_effect=fake_post),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            ai_service._chat([{"role": "user", "content": "x"}], **chat_kwargs)
        return seen["payload"]

    def test_chat_applies_headroom_to_max_tokens(self):
        """`_chat` 实际下发的 max_tokens 必须带上推理余量。"""
        payload = self._capture_payload(max_tokens=4000)
        self.assertEqual(payload["max_tokens"], int(4000 * ai_service._REASONING_TOKEN_HEADROOM))

    def test_no_max_tokens_means_provider_default(self):
        """不指定 max_tokens 时不要凭空塞一个上限。"""
        payload = self._capture_payload()
        self.assertNotIn("max_tokens", payload)

    def test_json_budget_passes_through_base(self):
        """`_json_chat_budget` 只返回基础预算（余量由 _chat 负责，避免重复放大）。"""
        self.assertEqual(ai_service._json_chat_budget(4000), 4000)
        self.assertEqual(ai_service._json_chat_budget(12000), 12000)
        self.assertEqual(ai_service._json_chat_budget(None), 8000)


class MechanicalThinkingOffTest(unittest.TestCase):
    """机械性任务关闭推理（think=False）的回归。

    背景：`deepseek-flash` 的推理 token 占输出 46-81%，是耗时与花费的主因。
    实测（同任务 A/B，项目真实 `_vision_extract_text`）：
      开推理 14.3s / 推理 3167 / 输出 3297 / 正文 210 字
      关推理  0.9s / 推理    0 / 输出  131 / 正文 229 字   （快 16 倍，token 省 25 倍，质量不降）
    所以"照抄/按 schema 抽取"这类任务显式关推理；分析类任务保持默认（开）。

    这两条断言把优化钉住，避免以后被无声改回：
      ① 关推理时必须真的下发 `thinking: {type: disabled}`；
      ② 关推理时**不许再乘 1.5 倍推理余量** —— 没有推理却放大 max_tokens
         等于按更大的上限计费（而且以前推理吃掉一半预算，正文反而更少）。
    """

    def _capture_payload(self, **chat_kwargs):
        seen = {}

        def fake_post(opener, request, timeout):
            seen["payload"] = json.loads(request.data.decode())
            return _resp("ok")

        with (
            patch.object(ai_service, "_post_chat", side_effect=fake_post),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            ai_service._chat([{"role": "user", "content": "x"}], **chat_kwargs)
        return seen["payload"]

    def test_thinking_off_sends_disabled_flag(self):
        payload = self._capture_payload(max_tokens=4000, thinking=False)
        self.assertEqual(payload.get("thinking"), {"type": "disabled"})

    def test_thinking_off_drops_reasoning_headroom(self):
        payload = self._capture_payload(max_tokens=4000, thinking=False)
        self.assertEqual(payload["max_tokens"], 4000)

    def test_thinking_on_keeps_headroom_and_no_flag(self):
        """默认（分析类任务）行为不变：有余量、不下发 thinking。"""
        payload = self._capture_payload(max_tokens=4000)
        self.assertNotIn("thinking", payload)
        self.assertEqual(payload["max_tokens"], int(4000 * ai_service._REASONING_TOKEN_HEADROOM))


class TruncationRetryTest(unittest.TestCase):
    """被截断时必须自动加大预算重试，而不是把残缺内容当成功交出去。"""

    def test_chat_retries_with_bigger_budget_on_length(self):
        budgets = []

        def fake_post(opener, request, timeout):
            payload = json.loads(request.data.decode())
            budgets.append(payload["max_tokens"])
            if len(budgets) == 1:
                # 第一轮：预算被推理吃光，正文空
                return _resp("", "length", reasoning=payload["max_tokens"] - 2)
            return _resp("完整正文", "stop", reasoning=10)

        with (
            patch.object(ai_service, "_post_chat", side_effect=fake_post),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            text, meta = ai_service._chat(
                [{"role": "user", "content": "x"}], max_tokens=4000, with_meta=True
            )

        self.assertEqual(text, "完整正文")
        self.assertFalse(meta["truncated"])
        self.assertEqual(len(budgets), 2, "应重试一次")
        self.assertGreater(budgets[1], budgets[0], "重试必须用更大预算")

    def test_chat_reports_truncation_when_retries_exhausted(self):
        """反复被截断时不能无限重试；最终结果要带 truncated 标记。"""

        def fake_post(opener, request, timeout):
            payload = json.loads(request.data.decode())
            return _resp("被截断的正文", "length", reasoning=payload["max_tokens"] - 2)

        with (
            patch.object(ai_service, "_post_chat", side_effect=fake_post),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            text, meta = ai_service._chat(
                [{"role": "user", "content": "x"}], max_tokens=1000, with_meta=True
            )

        self.assertTrue(meta["truncated"], "截断必须如实标记，调用方据此告警")
        self.assertTrue(text)

    def test_budget_never_exceeds_ceiling(self):
        budgets = []

        def fake_post(opener, request, timeout):
            payload = json.loads(request.data.decode())
            budgets.append(payload["max_tokens"])
            return _resp("", "length", reasoning=payload["max_tokens"])

        with (
            patch.object(ai_service, "_post_chat", side_effect=fake_post),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            ai_service._chat([{"role": "user", "content": "x"}], max_tokens=40000)

        self.assertTrue(all(b <= ai_service.MAX_TOKENS_CEILING for b in budgets), budgets)

    def test_plain_text_by_default(self):
        """默认返回纯字符串，不破坏既有调用点。"""
        with (
            patch.object(ai_service, "_post_chat", side_effect=lambda *a: _resp("hi")),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            self.assertEqual(ai_service._chat([{"role": "user", "content": "x"}]), "hi")


class ChatJsonTest(unittest.TestCase):
    def test_normal_path_returns_parsed_json(self):
        with (
            patch.object(ai_service, "_post_chat", side_effect=lambda *a: _resp('{"a": [1, 2]}')),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            self.assertEqual(
                ai_service._chat_json([{"role": "user", "content": "x"}]), {"a": [1, 2]}
            )

    def test_empty_without_length_fails_with_clear_message(self):
        with (
            patch.object(ai_service, "_post_chat", side_effect=lambda *a: _resp("", "stop")),
            patch.object(ai_service, "is_configured", return_value=True),
        ):
            with self.assertRaises(ai_service.AiRequestError) as ctx:
                ai_service._chat_json([{"role": "user", "content": "x"}], attempts=2)
        self.assertIn("内容为空", str(ctx.exception))


class VisionExtractionTest(unittest.TestCase):
    """识图提字：prompt 要把原文与题目分开，且预算不能写死得太小。"""

    def test_vision_prompt_separates_passage_and_questions(self):
        captured = {}

        def fake_chat(messages, with_meta=False, **kwargs):
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            content = "【原文】\nSome passage.\n\n【题目】\n1. Q?"
            if with_meta:
                return content, {"truncated": False, "finish_reason": "stop"}
            return content

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            ai_service._vision_extract_text(["AAAA"])

        head = captured["messages"][0]["content"][0]["text"]
        self.assertIn("【原文】", head)
        self.assertIn("【题目】", head)
        self.assertIn("完整", head)
        # 预算必须留足：历史 bug 写死 4000，被推理（实测单次识图约 12000 reasoning
        # tokens）吃掉后正文被静默截断，表现为"英语原文只识出一两段"
        self.assertGreaterEqual(captured["kwargs"].get("max_tokens", 0), 16000)

    def test_truncated_vision_result_is_logged(self):
        """识图被截断要打警告日志，便于发现"原文缺失"。"""
        with (
            patch.object(
                ai_service,
                "_chat",
                return_value=("残文", {"truncated": True, "finish_reason": "length"}),
            ),
            patch.object(ai_service.logger, "warning") as warn,
        ):
            ai_service._vision_extract_text(["AAAA"])
        self.assertTrue(warn.called, "截断必须记日志")

    def test_vision_result_is_stripped_text(self):
        """返回的是纯文本（不是 tuple），保持既有调用契约。"""

        def fake_chat(messages, with_meta=False, **kwargs):
            return "  正文  ", {"truncated": False}

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            out = ai_service._vision_extract_text(["AAAA"])
        self.assertEqual(out, "正文")


class SplitOcrSectionsTest(unittest.TestCase):
    """识图文本要能拆出「文章」与「题目」——不拆就会让 AI 改写题干。

    实测症状：原文里混着题干与选项，阅读步骤去翻译题目，题目步骤再靠 AI 重写题目，
    于是"分析出来的题目与给出的题目完全不一致"。
    """

    SAMPLE = (
        "【原文】\n"
        "The great recession may be over.\n"
        "Before it ends, it will change things.\n"
        "\n"
        "【题目】\n"
        "1. According to Paragraph 1, people _____\n"
        "A) a  B) b  C) c  D) d\n"
    )

    def test_splits_passage_and_questions(self):
        passage, quiz = ai_service._split_ocr_sections(self.SAMPLE)
        self.assertIn("great recession", passage)
        self.assertNotIn("According to Paragraph 1", passage, "文章里不应混入题干")
        self.assertNotIn("A) a", passage, "文章里不应混入选项")
        self.assertIn("According to Paragraph 1", quiz)
        self.assertIn("A) a", quiz)

    def test_english_marker_variants(self):
        for marker in ("【原文】", "[原文]", "【文章】", "【正文】"):
            passage, quiz = ai_service._split_ocr_sections(
                f"{marker}\nPassage body here.\n【题目】\n1. Q?"
            )
            self.assertIn("Passage body here", passage, marker)
            self.assertIn("1. Q?", quiz, marker)

    def test_no_marker_falls_back_to_whole_text(self):
        """识别不到小标题时不能丢内容（旧行为兼容）。"""
        passage, quiz = ai_service._split_ocr_sections("just some text")
        self.assertEqual(passage, "just some text")
        self.assertEqual(quiz, "just some text")

    def test_questions_only_still_returns_content(self):
        """只截到题目页时，两边都返回题目，避免正文为空。"""
        passage, quiz = ai_service._split_ocr_sections("【题目】\n1. Q?")
        self.assertIn("1. Q?", passage)
        self.assertIn("1. Q?", quiz)

    def test_empty_input_safe(self):
        self.assertEqual(ai_service._split_ocr_sections(""), ("", ""))
        self.assertEqual(ai_service._split_ocr_sections(None), ("", ""))


if __name__ == "__main__":
    unittest.main()
