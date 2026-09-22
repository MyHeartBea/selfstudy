"""/images 路径的口令守门 + token 多来源（header/cookie/query）。

未设 API_TOKEN 时全放行（单机零配置）；设了之后 /api 走 router 依赖、/images 走
中间件 —— `<img>` 标签发不了自定义头，cookie/query 必须也被接受，
否则"设了 token 图全挂"这个缺口等于没修（前端 boot 时把 token 写进 km_token cookie）。

404 在这里算"放行成功"的证据：中间件放行后请求落到静态/缩略图处理器，
文件不存在才 404；401 则说明被守门拦下。
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


class ImagesTokenGuardTest(unittest.TestCase):
    """settings.API_TOKEN 已设为 secret-token 的模式。"""

    def setUp(self):
        patcher = patch.object(settings, "API_TOKEN", "secret-token")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_images_without_token_rejected(self):
        self.assertEqual(client.get("/images/nope.png").status_code, 401)
        self.assertEqual(client.get("/images/thumb/nope.png").status_code, 401)

    def test_header_accepted(self):
        headers = {"X-API-Token": "secret-token"}
        self.assertEqual(client.get("/images/nope.png", headers=headers).status_code, 404)
        self.assertEqual(client.get("/images/thumb/nope.png", headers=headers).status_code, 404)
        r = client.get("/api/exam-countdown", headers=headers)
        self.assertEqual(r.status_code, 200)

    def test_cookie_accepted_for_images_and_api(self):
        client.cookies.set("km_token", "secret-token")
        try:
            self.assertEqual(client.get("/images/nope.png").status_code, 404)
            r = client.get("/api/exam-countdown")
            self.assertEqual(r.status_code, 200)
        finally:
            client.cookies.clear()

    def test_query_param_accepted_for_images(self):
        r = client.get("/images/nope.png?api_token=secret-token")
        self.assertEqual(r.status_code, 404)

    def test_wrong_token_rejected(self):
        self.assertEqual(client.get("/images/nope.png?api_token=wrong").status_code, 401)
        r = client.get("/api/exam-countdown", headers={"X-API-Token": "wrong"})
        self.assertEqual(r.status_code, 401)


class NoTokenModeTest(unittest.TestCase):
    """单机零配置：不设 token 时一切照旧。"""

    def setUp(self):
        patcher = patch.object(settings, "API_TOKEN", "")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_everything_open(self):
        self.assertEqual(client.get("/images/nope.png").status_code, 404)
        self.assertEqual(client.get("/api/exam-countdown").status_code, 200)
