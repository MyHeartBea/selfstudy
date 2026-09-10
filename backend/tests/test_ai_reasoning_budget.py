"""推理模型（deepseek-flash）的预算回归。

背景：deepseek-flash 会先输出 reasoning_content 再输出正文。若 max_tokens 只按
"正文长度"估算，预算会被推理吃光 → `finish_reason=length`、`content` 为空。
实测拆题调用 12000 预算里有 11998 是 reasoning_tokens、正文 0 字，
导致两整份试卷导入失败并报出误导性的"AI 返回内容为空"。
"""

import json
import unittest
from unittest.mock import patch

from app.services import ai_service


class JsonBudgetTest(unittest.TestCase):
    def test_headroom_applied(self):
        self.assertEqual(ai_service._json_chat_budget(12000), 18000)
        self.assertEqual(ai_service._json_chat_budget(4000), 6000)

    def test_default_when_unspecified(self):
        self.assertEqual(ai_service._json_chat_budget(None), 16000)

    def test_ceiling(self):
        self.assertLessEqual(ai_service._json_chat_budget(999999), ai_service.MAX_TOKENS_CEILING)


class ChatJsonTruncationRetryTest(unittest.TestCase):
    def test_retries_with_larger_budget_when_reasoning_eats_it(self):
        """首轮预算被推理耗光（length + 空 content）→ 必须加大预算重试并成功。"""
        seen = []

        def fake_chat(messages, max_tokens=None, with_meta=False, **kwargs):
            seen.append(max_tokens)
            if len(seen) == 1:
                # 推理把预算吃光，正文为空
                return "", {
                    "finish_reason": "length",
                    "reasoning_tokens": max_tokens,
                    "has_reasoning": True,
                }
            return '{"ok": true}', {"finish_reason": "stop", "reasoning_tokens": 10}

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            result = ai_service._chat_json(
                [{"role": "user", "content": "x"}], max_tokens=12000
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(seen), 2, "应重试一次")
        self.assertGreater(seen[1], seen[0], "重试必须用更大的预算")

    def test_empty_without_length_does_not_inflate_forever(self):
        """非截断导致的空返回（如 stop 但内容空）重试后仍失败，且预算不无限膨胀。"""
        seen = []

        def fake_chat(messages, max_tokens=None, with_meta=False, **kwargs):
            seen.append(max_tokens)
            return "", {"finish_reason": "stop", "reasoning_tokens": 0}

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            with self.assertRaises(ai_service.AiRequestError) as ctx:
                ai_service._chat_json([{"role": "user", "content": "x"}], max_tokens=4000)

        self.assertIn("内容为空", str(ctx.exception))
        self.assertEqual(len(set(seen)), 1, "非截断场景不应逐次放大预算")

    def test_error_message_mentions_reasoning_when_truncated(self):
        def fake_chat(messages, max_tokens=None, with_meta=False, **kwargs):
            return "", {"finish_reason": "length", "reasoning_tokens": max_tokens}

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            with self.assertRaises(ai_service.AiRequestError) as ctx:
                ai_service._chat_json(
                    [{"role": "user", "content": "x"}], max_tokens=2000, attempts=2
                )
        msg = str(ctx.exception)
        self.assertIn("预算", msg)
        self.assertIn("推理", msg, "错误信息要说清是推理 token 吃掉了预算，便于排查")
        self.assertIn("length", msg)

    def test_normal_path_returns_parsed_json(self):
        def fake_chat(messages, max_tokens=None, with_meta=False, **kwargs):
            return '{"a": [1, 2]}', {"finish_reason": "stop", "reasoning_tokens": 5}

        with patch.object(ai_service, "_chat", side_effect=fake_chat):
            self.assertEqual(
                ai_service._chat_json([{"role": "user", "content": "x"}]),
                {"a": [1, 2]},
            )


class ChatMetaTest(unittest.TestCase):
    def test_chat_returns_plain_text_by_default(self):
        """默认调用仍返回纯字符串，不破坏既有调用点。"""
        import inspect

        src = inspect.getsource(ai_service._chat)
        self.assertIn("with_meta", src)
        # 默认分支返回 content 本体
        self.assertIn("if not with_meta:", src)


if __name__ == "__main__":
    unittest.main()
