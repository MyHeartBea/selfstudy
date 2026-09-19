"""工程项回归：HOST 可配、快照（导入/批量删除前）、请求监控计数。"""

import os
import sqlite3
import unittest
from unittest.mock import patch

from app import metrics
from app.config import settings


class HostConfigTest(unittest.TestCase):
    def test_host_reads_env_with_localhost_default(self):
        """HOST 必须可被 .env/环境变量覆盖，默认仍是只监听本机。"""
        import importlib

        import app.config as config_module

        original = os.environ.get("HOST")
        try:
            os.environ["HOST"] = "0.0.0.0"
            importlib.reload(config_module)
            self.assertEqual(config_module.Settings.HOST, "0.0.0.0")

            os.environ.pop("HOST", None)
            importlib.reload(config_module)
            self.assertEqual(config_module.Settings.HOST, "127.0.0.1")
        finally:
            if original is None:
                os.environ.pop("HOST", None)
            else:
                os.environ["HOST"] = original
            importlib.reload(config_module)

    def test_review_daily_limit_default(self):
        self.assertGreater(settings.REVIEW_DAILY_LIMIT, 0)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory(
            dir=r"D:\temp" if os.path.isdir(r"D:\temp") else None
        )
        self.db_path = Path(self.tmp.name) / "kaoyan_mistakes.db"
        self.backup_dir = Path(self.tmp.name) / "backups"
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.execute("INSERT INTO t (v) VALUES ('原始数据')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_creates_restorable_copy(self):
        from app import database

        with (
            patch.object(database.settings, "DB_PATH", self.db_path),
            patch.object(database.settings, "BACKUP_DIR", self.backup_dir),
            patch.object(database.settings, "MAX_BACKUPS", 20),
        ):
            name = database.snapshot_database("before-import-3")
            self.assertTrue(name and name.endswith(".db"))
            self.assertIn("before-import-3", name)

            # 快照内容可读且与源一致
            snap = self.backup_dir / name
            self.assertTrue(snap.exists())
            conn = sqlite3.connect(snap)
            self.assertEqual(conn.execute("SELECT v FROM t").fetchone()[0], "原始数据")
            conn.close()

            listed = database.list_snapshots()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["name"], name)
            self.assertGreater(listed[0]["size_kb"], 0)

    def test_snapshot_missing_db_returns_none(self):
        from pathlib import Path

        from app import database

        with patch.object(database.settings, "DB_PATH", Path(self.tmp.name) / "nope.db"):
            self.assertIsNone(database.snapshot_database("x"))

    def test_snapshot_keeps_recent_and_prunes_old(self):
        from app import database

        with (
            patch.object(database.settings, "DB_PATH", self.db_path),
            patch.object(database.settings, "BACKUP_DIR", self.backup_dir),
            patch.object(database.settings, "MAX_BACKUPS", 3),
        ):
            for i in range(6):
                database.snapshot_database(f"n{i}")
            files = list(self.backup_dir.glob("kaoyan_mistakes_*.db"))
            self.assertLessEqual(len(files), 3, "超过 MAX_BACKUPS 的旧快照应被清理")


class MetricsTest(unittest.TestCase):
    def setUp(self):
        metrics.reset()

    def test_counts_and_normalizes_id_paths(self):
        metrics.record("GET", "/api/mistakes/12", 200, 10.0)
        metrics.record("GET", "/api/mistakes/99", 200, 20.0)
        snap = metrics.snapshot()
        self.assertEqual(snap["requests_total"], 2)
        # 数字 id 归一化后应合并成一条统计
        endpoints = [e["endpoint"] for e in snap["slowest_endpoints"]]
        self.assertIn("GET /api/mistakes/{id}", endpoints)
        self.assertEqual(snap["errors_total"], 0)

    def test_error_and_slow_recorded(self):
        metrics.record("POST", "/api/ai/analyze", 502, 50.0)
        metrics.record("GET", "/api/slow", 200, settings.SLOW_REQUEST_MS + 500)
        snap = metrics.snapshot()
        self.assertEqual(snap["errors_total"], 1)
        self.assertEqual(snap["slow_total"], 1)
        self.assertEqual(snap["recent_errors"][0]["status"], 502)
        self.assertTrue(snap["slowest_requests"])
        self.assertGreaterEqual(snap["slowest_requests"][0]["ms"], settings.SLOW_REQUEST_MS)

    def test_429_counted_separately_from_errors(self):
        """限流不是 5xx（不该污染 recent_errors），但必须能被数出来。"""
        for _ in range(3):
            metrics.record("POST", "/api/ai/ocr", 429, 12.0)
        metrics.record("POST", "/api/ai/ocr", 200, 12.0)
        snap = metrics.snapshot()
        self.assertEqual(snap["throttled_total"], 3)
        self.assertEqual(snap["errors_total"], 0)
        self.assertEqual(snap["recent_errors"], [])

    def test_record_ai_aggregates_per_channel(self):
        metrics.record_ai("deepseek-flash", "https://api.deepseek.com/v1", 100.0)
        metrics.record_ai("deepseek-flash", "https://api.deepseek.com/v1", 300.0)
        metrics.record_ai(
            "glm-4.6v-flash",
            "https://open.bigmodel.cn/api/paas/v4",
            50.0,
            ok=False,
            error="AI 服务返回 401: bad key",
        )
        by_model = {row["channel"]: row for row in metrics.snapshot()["ai"]["by_model"]}
        ds = by_model["deepseek-flash @ api.deepseek.com"]
        self.assertEqual(
            (ds["calls"], ds["errors"], ds["avg_ms"], ds["max_ms"]), (2, 0, 200.0, 300.0)
        )
        self.assertEqual(ds["last_error"], "", "成功通道不该挂着别人的错误")
        glm = by_model["glm-4.6v-flash @ open.bigmodel.cn"]
        self.assertEqual((glm["calls"], glm["errors"]), (1, 1))
        self.assertIn("401", glm["last_error"])
        self.assertTrue(glm["last_error_at"])
        summary = metrics.snapshot()["ai"]
        self.assertEqual(summary["calls_total"], 3)
        self.assertEqual(summary["errors_total"], 1)

    def test_record_ai_masks_keys_in_last_error(self):
        """/api/health 是可读端点：上游报错里的密钥必须在入库前打掉，不是展示时。"""
        secret = "sk-" + "a" * 24
        metrics.record_ai(
            "m",
            "https://api.deepseek.com/v1",
            10.0,
            ok=False,
            error=f"AI 服务返回 401: {{'error': {{'message': 'Invalid Authentication', 'key': '{secret}'}}}}",
        )
        metrics.record_ai(
            "m2",
            "https://x.test/v1",
            10.0,
            ok=False,
            error=f"请求头 Authorization: Bearer {secret[3:]} 被网关回显",
        )
        rows = {row["channel"]: row for row in metrics.snapshot()["ai"]["by_model"]}
        for channel in ("m @ api.deepseek.com", "m2 @ x.test"):
            self.assertNotIn(secret, rows[channel]["last_error"], "密钥原文不得出现在监控里")
            self.assertNotIn(secret[3:], rows[channel]["last_error"])
            self.assertIn("****", rows[channel]["last_error"])

    def test_record_ai_counts_truncation_and_reasoning(self):
        metrics.record_ai("m", "https://x.test/v1", 10.0, truncated=True, reasoning_tokens=9000)
        metrics.record_ai("m", "https://x.test/v1", 10.0, reasoning_tokens=1000)
        row = metrics.snapshot()["ai"]["by_model"][0]
        self.assertEqual(row["truncated"], 1)
        self.assertEqual(row["reasoning_avg"], 5000)
        self.assertEqual(metrics.snapshot()["ai"]["truncated_total"], 1)

    def test_reset_clears_ai_and_throttle(self):
        metrics.record("POST", "/api/ai/ocr", 429, 1.0)
        metrics.record_ai("m", "https://x.test/v1", 1.0, ok=False, error="boom")
        metrics.reset()
        snap = metrics.snapshot()
        self.assertEqual(snap["throttled_total"], 0)
        self.assertEqual(snap["ai"]["by_model"], [])
        self.assertEqual(snap["ai"]["calls_total"], 0)


if __name__ == "__main__":
    unittest.main()
