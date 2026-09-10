"""多图提文字（知识点粘贴多张截图）链路的回归测试。

覆盖三件事：
1. `vision_extract_text_multi` 按批切分、保留图片顺序、逐批失败不整体中断；
2. `AiOcrRequest` 的 image_base64 / images 双入口（老单图调用不被破坏）；
3. `/api/ai/knowledge-from-image` 收多图时只做「一次」知识点整理，
   不会退化成"每张图各出一条草稿"。

全程 mock `ai_service._chat`，不发起任何真实 AI 调用。
"""

import json
import unittest
from unittest.mock import patch

from app.schemas import AiOcrRequest
from app.services import ai_service


def fake_chat_factory(calls, vision_texts=None):
    """返回一个假的 _chat：视觉调用返回预置文本，文本整理返回知识点 JSON。"""
    vision_iter = iter(vision_texts or [])
    vision_calls = []

    def fake_chat(messages, model=None, base_url=None, api_key=None, max_tokens=None, timeout=None):
        content = messages[0]["content"]
        if isinstance(content, list):
            # 视觉提文字：记录本次带了几张图
            n_images = sum(1 for part in content if part.get("type") == "image_url")
            vision_calls.append(n_images)
            calls.append(n_images)
            try:
                return next(vision_iter)
            except StopIteration:
                return ""
        # 文本整理（analyze_knowledge）
        return (
            '{"tag_name": "合并知识点", "summary": "合并后的摘要", '
            '"related_tags": ["A", "B"]}'
        )

    return fake_chat, vision_calls


class MultiImageExtractTest(unittest.TestCase):
    def test_single_image_uses_single_call(self):
        calls = []
        fake, vision_calls = fake_chat_factory(calls, ["单图文字"])
        with patch.object(ai_service, "_chat", side_effect=fake):
            text = ai_service.vision_extract_text_multi(["img1"])
        self.assertIn("单图文字", text)
        # 单图不加【第N张】标签，保持和旧行为一致的纯文本
        self.assertNotIn("【第1张】", text)
        self.assertEqual(vision_calls, [1])

    def test_multiple_images_are_batched_and_ordered(self):
        fake, vision_calls = fake_chat_factory([], ["批一", "批二", "批三"])
        images = [f"img{i}" for i in range(1, 8)]  # 7 张 → 3 批（3/3/1）
        with patch.object(ai_service, "_chat", side_effect=fake):
            text = ai_service.vision_extract_text_multi(images)

        self.assertEqual(vision_calls, [3, 3, 1], "应按 VISION_BATCH_SIZE 分批")
        # 顺序必须与粘贴顺序一致
        self.assertLess(text.index("【第1-3张】"), text.index("【第4-6张】"))
        self.assertLess(text.index("【第4-6张】"), text.index("【第7张】"))
        self.assertIn("批一", text)
        self.assertIn("批三", text)

    def test_empty_images_returns_empty_without_calling_ai(self):
        def explode(*args, **kwargs):
            raise AssertionError("空图片列表不应调用 _chat")

        with patch.object(ai_service, "_chat", side_effect=explode):
            self.assertEqual(ai_service.vision_extract_text_multi([]), "")
            self.assertEqual(ai_service.vision_extract_text_multi(["", "   "]), "")

    def test_failed_batch_keeps_the_rest(self):
        """某一批识别失败时，其余批次内容仍要保留并标注失败批次。"""
        state = {"n": 0}

        def flaky_chat(messages, **kwargs):
            content = messages[0]["content"]
            if isinstance(content, list):
                state["n"] += 1
                if state["n"] == 2:
                    raise RuntimeError("模拟第二批超时")
                return f"第{state['n']}批文字"
            return '{"tag_name": "t", "summary": "s", "related_tags": []}'

        images = [f"img{i}" for i in range(1, 7)]  # 2 批
        with patch.object(ai_service, "_chat", side_effect=flaky_chat):
            text = ai_service.vision_extract_text_multi(images)

        self.assertIn("第1批文字", text)
        self.assertIn("未能识别", text)
        self.assertIn("第4-6张", text)


class OcrRequestSchemaTest(unittest.TestCase):
    def test_legacy_single_image_still_valid(self):
        body = AiOcrRequest(image_base64="abc")
        self.assertEqual(body.image_base64, "abc")
        self.assertEqual(body.images, [])

    def test_multi_image_accepted(self):
        body = AiOcrRequest(images=["a", "b", "c"])
        self.assertEqual(len(body.images), 3)

    def test_neither_image_rejected(self):
        with self.assertRaises(Exception):
            AiOcrRequest()


def _body_of(resp) -> dict:
    """把路由返回值统一成 dict。

    直接调用路由处理函数时，成功走 `ok()`（普通 dict），但**未配置 AI 时会走
    `error()` 返回 `JSONResponse`**。CI 上没有 backend/.env，`is_configured()` 为 False，
    于是这里拿到的是 JSONResponse —— 旧写法 `resp["code"]` 会抛
    `TypeError: 'JSONResponse' object is not subscriptable`（CI 红了 6 次就是这个）。
    """
    if isinstance(resp, dict):
        return resp
    body = getattr(resp, "body", None)
    if body is not None:
        return json.loads(body.decode("utf-8"))
    raise AssertionError(f"无法解析的响应类型：{type(resp).__name__}")


class KnowledgeFromImageRouteTest(unittest.TestCase):
    """路由层：多图 → 一次整理（不会每张各写一条知识点）。"""

    def _call(self, body):
        from app.routers import ai as ai_router

        return _body_of(ai_router.knowledge_from_image(body))

    def _patch_ai(self, **analyze):
        """同时假装「AI 已配置 + 有视觉通道」并替换提字/整理两步。

        CI 上没有 backend/.env，会连环踩两个坑：
        1. `is_configured()` 为 False → 路由直接返回 400「未配置 AI 服务」；
        2. 即使放行，`_vision_providers()` 也会因为没 key 返回空列表，
           `_vision_extract_with_fallback` 根本不会调用提字函数 → 502。
        所以这三处都要打桩，测试才真正跑在多图逻辑上。
        """
        from app.routers import ai as ai_router

        return [
            patch.object(ai_router.ai_service, "is_configured", return_value=True),
            patch.object(
                ai_router,
                "_vision_providers",
                return_value=[("fake-vision", None, None)],
            ),
            patch.object(ai_router.ai_service, "vision_extract_text_multi", **analyze["extract"]),
            patch.object(ai_router.ai_service, "analyze_knowledge", **analyze["analyze"]),
            patch("app.routers.ai.local_ocr.is_available", return_value=False),
        ]

    def test_multi_image_produces_one_draft(self):
        analyze_calls = []

        def fake_analyze(text, instruction=""):
            analyze_calls.append(text)
            return {"tag_name": "合并知识点", "summary": "摘要", "related_tags": []}

        def fake_extract(images, instruction="", **kwargs):
            self.assertEqual(len(images), 3, "应把 3 张图交给同一次提取")
            return "【第1-3张】\n文字内容"

        patches = self._patch_ai(
            extract={"side_effect": fake_extract},
            analyze={"side_effect": fake_analyze},
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        resp = self._call(AiOcrRequest(images=["a", "b", "c"]))

        self.assertEqual(resp["code"], 200, f"响应异常：{resp.get('message')}")
        self.assertEqual(resp["data"]["tag_name"], "合并知识点")
        self.assertEqual(len(analyze_calls), 1, "多图只应整理一次")

    def test_legacy_single_image_body_still_works(self):
        def fake_extract(images, instruction="", **kwargs):
            self.assertEqual(images, ["solo"])
            return "文字"

        patches = self._patch_ai(
            extract={"side_effect": fake_extract},
            analyze={"return_value": {"tag_name": "t", "summary": "s", "related_tags": []}},
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        resp = self._call(AiOcrRequest(image_base64="solo"))
        self.assertEqual(resp["code"], 200, f"响应异常：{resp.get('message')}")

    def test_unconfigured_ai_returns_readable_error(self):
        """没配 AI 时必须返回结构化错误（而不是抛异常），前端才能提示配置方式。"""
        from app.routers import ai as ai_router

        with patch.object(ai_router.ai_service, "is_configured", return_value=False):
            resp = ai_router.knowledge_from_image(AiOcrRequest(images=["a"]))
        body = _body_of(resp)
        self.assertNotEqual(body["code"], 200)
        self.assertTrue(body.get("message"))


def ai_router_service():
    """路由模块里引用的 ai_service（便于 patch 到同一对象）。"""
    from app.routers import ai as ai_router

    return ai_router.ai_service


if __name__ == "__main__":
    unittest.main()
