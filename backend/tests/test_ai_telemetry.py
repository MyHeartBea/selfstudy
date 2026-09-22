"""AI 通道遥测：`_chat` 的每一次调用（成功 / 抛错 / 空返回 / 截断重试）都要留一行账。

这批测试钉的是**可观测性契约**，不是模型行为：视觉多通道按序回退时，前一个通道的
异常会被后一个通道的成功掩盖（`routers/ai.py` 只把异常留在局部变量里），过去只能靠
"识图变慢了"察觉。现在 `/api/health` 的 `metrics.ai.by_model` 必须逐通道写明调了几次、
错了几次、最后一次错什么 —— 所以：
1. 失败**必须**与成功同样入账（漏记 = 这个功能白做）；
2. 一次 `_chat` **恰好**一条记录（内部 4 轮翻倍重试不能记成 4 次调用，否则错误率失真）；
3. 报错文本进监控前必须脱敏（`/api/health` 是能被读到的端点）。

模型名与端点一律 patch 成固定值：CI 没有 `backend/.env`，`AI_BASE_URL` 的兜底默认是
`api.openai.com`、本机却是 `api.deepseek.com`，用真实配置拼通道名会让两边只能绿一边。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import metrics
from app.config import settings
from app.services import ai_service
from app.services.ai_service import AiNotConfigured, AiRequestError

MODEL = "unit-model"
BASE_URL = "https://unit.test/v1"
CHANNEL = f"{MODEL} @ unit.test"

# 通道成功时返回的最小可用解析结果（字段名按接口响应形状，不是 LLM 入参形状）
_ENGLISH = {
    "is_english": True,
    "subject_hint": "英语",
    "passage_text": "This is a passage.",
    "passage_translation": "这是一段文章。",
    "english_sentences": [],
    "english_phrases": [],
    "english_words": [],
    "english_questions": [],
}


def chat_response(content="", finish_reason="stop", reasoning=0, completion=0):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {
            "completion_tokens": completion,
            "completion_tokens_details": {"reasoning_tokens": reasoning},
        },
    }


class ChatTelemetryTest(unittest.TestCase):
    def setUp(self):
        metrics.reset()
        # CI 没有 backend/.env：不塞一把假 key，is_configured() 直接 False，测不到请求
        self._patcher = (
            patch.object(ai_service.settings, "AI_API_KEY", "sk-test-not-a-real-key"),
            patch.object(ai_service.settings, "AI_MODEL", MODEL),
            patch.object(ai_service.settings, "AI_BASE_URL", BASE_URL),
        )
        for ctx in self._patcher:
            ctx.start()

    def tearDown(self):
        for ctx in self._patcher:
            ctx.stop()
        metrics.reset()

    def rows(self):
        return {row["channel"]: row for row in metrics.snapshot()["ai"]["by_model"]}

    def test_success_records_one_row(self):
        with patch.object(
            ai_service, "_post_chat", return_value=chat_response("答案", "stop", 120, 30)
        ):
            self.assertEqual(ai_service._chat([{"role": "user", "content": "hi"}]), "答案")
        row = self.rows()[CHANNEL]
        self.assertEqual((row["calls"], row["errors"], row["truncated"]), (1, 0, 0))
        self.assertEqual(row["reasoning_avg"], 120)
        self.assertEqual(row["last_error"], "")

    def test_channel_key_is_model_plus_host(self):
        """兜底通道要单独成行：合并成一行就看不出"首选在报错、兜底在干活"。"""
        with patch.object(ai_service, "_post_chat", return_value=chat_response("ok", "stop")):
            ai_service._chat(
                [{"role": "user", "content": "hi"}],
                model="glm-4.6v-flash",
                base_url="https://open.bigmodel.cn/api/paas/v4",
            )
        self.assertEqual(list(self.rows()), ["glm-4.6v-flash @ open.bigmodel.cn"])

    def test_exception_is_recorded_and_reraised(self):
        boom = AiRequestError("AI 服务返回 401: Invalid Authentication, key sk-abcd1234efgh5678")
        with patch.object(ai_service, "_post_chat", side_effect=boom):
            with self.assertRaises(AiRequestError):
                ai_service._chat([{"role": "user", "content": "hi"}])
        row = self.rows()[CHANNEL]
        self.assertEqual((row["calls"], row["errors"]), (1, 1))
        self.assertNotIn("sk-abcd1234efgh5678", row["last_error"], "监控里不许有密钥原文")
        self.assertIn("****", row["last_error"])

    def test_empty_content_counts_as_error(self):
        """推理吃光预算后 HTTP 200 + 空正文：这是最容易被漏掉的一种失败。"""
        with patch.object(ai_service, "_post_chat", return_value=chat_response("", "stop")):
            ai_service._chat([{"role": "user", "content": "hi"}])
        row = self.rows()[CHANNEL]
        self.assertEqual((row["calls"], row["errors"]), (1, 1))
        self.assertIn("输出为空", row["last_error"])

    def test_truncation_retries_report_a_single_row(self):
        with patch.object(
            ai_service, "_post_chat", return_value=chat_response("半截", "length", 11998, 12000)
        ) as post:
            content, meta = ai_service._chat(
                [{"role": "user", "content": "hi"}], max_tokens=1000, with_meta=True
            )
        self.assertEqual(post.call_count, 4, "截断应翻倍预算重试")
        self.assertTrue(meta["truncated"])
        row = self.rows()[CHANNEL]
        # 4 次 HTTP 尝试 = 1 条通道记录：口径是"这个通道交付一份结果"，不是 TCP 次数
        self.assertEqual((row["calls"], row["errors"], row["truncated"]), (1, 0, 1))
        self.assertEqual(content, "半截")

    def test_not_configured_is_not_a_channel_failure(self):
        with (
            patch.object(ai_service.settings, "AI_API_KEY", ""),
            patch.object(ai_service.settings, "AI_VISION_API_KEY", ""),
        ):
            with self.assertRaises(AiNotConfigured):
                ai_service._chat([{"role": "user", "content": "hi"}])
        self.assertEqual(metrics.snapshot()["ai"]["by_model"], [])

    def test_health_exposes_ai_channels(self):
        """/api/health 是这些账的唯一出口，接不上等于没记。"""
        from fastapi.testclient import TestClient

        from app.main import app

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with (
            patch.object(settings, "DB_PATH", Path(tmp.name) / "t.db"),
            patch.object(settings, "BACKUP_DIR", Path(tmp.name) / "backups"),
        ):
            with patch.object(ai_service, "_post_chat", return_value=chat_response("答案", "stop")):
                ai_service._chat([{"role": "user", "content": "hi"}])
            with TestClient(app) as client:
                data = client.get("/api/health").json()["data"]
        channels = [row["channel"] for row in data["metrics"]["ai"]["by_model"]]
        self.assertIn(CHANNEL, channels)
        self.assertIn("throttled_total", data["metrics"])


class RouterDegradeTest(unittest.TestCase):
    """降级必须在响应的 `message` 里留痕 —— 前端 CaptureView 靠"已降级"决定要不要提醒。

    只验后端一半：`metrics.ai` 记账（上一类）+ message 带通道名（这一类）。
    """

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient

        from app.main import app

        cls._tmp = tempfile.TemporaryDirectory()
        cls._db = patch.object(settings, "DB_PATH", Path(cls._tmp.name) / "t.db")
        cls._bk = patch.object(settings, "BACKUP_DIR", Path(cls._tmp.name) / "backups")
        cls._db.start()
        cls._bk.start()
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)
        cls._bk.stop()
        cls._db.stop()
        cls._tmp.cleanup()

    @staticmethod
    def _flaky(primary_model, ok_payload):
        """首选通道抛，兜底通道成功：这正是"模型名过期/额度耗尽"的真实形状。"""

        def call(*args, **kwargs):
            if kwargs.get("model") == primary_model:
                raise AiRequestError("AI 服务返回 401: This model no longer exists")
            return ok_payload

        return call

    def _post(self, path, payload, target, providers):
        from app.routers import ai as ai_router

        with (
            patch.object(
                ai_router,
                "_vision_providers",
                return_value=[(p, None, None) for p in providers],
            ),
            patch.object(
                ai_router.ai_service, target, side_effect=self._flaky(providers[0], _ENGLISH)
            ),
            patch("app.routers.ai.local_ocr.is_available", return_value=False),
        ):
            return self.client.post(path, json=payload)

    def test_english_message_names_the_failed_channel(self):
        r = self._post(
            "/api/ai/english",
            {"images": ["a"], "text": ""},
            "analyze_english",
            ["stale-model", "backup-model"],
        )
        self.assertEqual(r.status_code, 200, r.text)
        message = r.json()["message"]
        self.assertIn("已降级", message)
        self.assertIn("stale-model", message, "要能看出是哪个通道挂了")
        self.assertNotIn("backup-model", message, "成功的通道不算降级")

    def test_ocr_message_names_the_failed_channel(self):
        r = self._post(
            "/api/ai/ocr",
            {"image_base64": "a"},
            "ocr_image",
            ["stale-model", "backup-model"],
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("已降级", r.json()["message"])

    def test_no_note_when_the_first_channel_answers(self):
        from app.routers import ai as ai_router

        with (
            patch.object(ai_router, "_vision_providers", return_value=[("only", None, None)]),
            patch.object(ai_router.ai_service, "analyze_english", return_value=dict(_ENGLISH)),
        ):
            r = self.client.post("/api/ai/english", json={"images": ["a"], "text": ""})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("降级", r.json()["message"], "没降级就别吓用户")


class SenseRateLimitPinTest(unittest.TestCase):
    """/api/ai/sense 是 AI 出口，必须挂 ai_rate_limit（曾是唯一漏挂的 AI 端点）。"""

    def test_sense_route_has_rate_limit(self):
        from app.routers.ai import router
        from app.security import ai_rate_limit

        routes = [r for r in router.routes if getattr(r, "path", "").endswith("/sense")]
        self.assertEqual(len(routes), 1)
        self.assertTrue(any(d.dependency is ai_rate_limit for d in routes[0].dependencies))


if __name__ == "__main__":
    unittest.main()


class CacheHitMetricsTest(unittest.TestCase):
    """前缀缓存命中的可见性：命中部分约 1/10 价，所以命中率必须能从 /api/health 读出来。

    背景：DeepSeek 的自动前缀缓存实测**确实在工作**（应用真实流程里逐题调用的命中量
    从 128 递增到 384，整体命中率 50%），但此前 `metrics` 里**完全没有这个口径** ——
    于是"缓存有没有生效"只能靠猜。这组用例把三个数的口径钉住。
    """

    def setUp(self):
        metrics.reset()

    def test_accumulates_prompt_and_cache_tokens(self):
        metrics.record_ai(
            "m", "https://api.deepseek.com/v1", 100.0, prompt_tokens=1000, cache_hit_tokens=400
        )
        metrics.record_ai(
            "m", "https://api.deepseek.com/v1", 100.0, prompt_tokens=1000, cache_hit_tokens=600
        )
        ch = metrics.snapshot()["ai"]["by_model"][0]
        self.assertEqual(ch["prompt_avg"], 1000)
        self.assertEqual(ch["cache_hit_avg"], 500)
        self.assertEqual(ch["cache_hit_pct"], 50)

    def test_zero_prompt_tokens_does_not_divide_by_zero(self):
        metrics.record_ai("m", "https://api.deepseek.com/v1", 10.0)
        ch = metrics.snapshot()["ai"]["by_model"][0]
        self.assertEqual(ch["cache_hit_pct"], 0)
        self.assertEqual(ch["prompt_avg"], 0)

    def test_missing_usage_fields_default_to_zero(self):
        """上游没回 usage 时不能炸，也不能把缺字段算成命中。"""
        metrics.record_ai(
            "m", "https://api.deepseek.com/v1", 10.0, prompt_tokens=None, cache_hit_tokens=None
        )
        ch = metrics.snapshot()["ai"]["by_model"][0]
        self.assertEqual(ch["cache_hit_avg"], 0)
