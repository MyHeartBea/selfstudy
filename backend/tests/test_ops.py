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

        self.tmp = tempfile.TemporaryDirectory(dir=r"D:\temp" if os.path.isdir(r"D:\temp") else None)
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

        with patch.object(database.settings, "DB_PATH", self.db_path), patch.object(
            database.settings, "BACKUP_DIR", self.backup_dir
        ), patch.object(database.settings, "MAX_BACKUPS", 20):
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
        from app import database
        from pathlib import Path

        with patch.object(database.settings, "DB_PATH", Path(self.tmp.name) / "nope.db"):
            self.assertIsNone(database.snapshot_database("x"))

    def test_snapshot_keeps_recent_and_prunes_old(self):
        from app import database

        with patch.object(database.settings, "DB_PATH", self.db_path), patch.object(
            database.settings, "BACKUP_DIR", self.backup_dir
        ), patch.object(database.settings, "MAX_BACKUPS", 3):
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


if __name__ == "__main__":
    unittest.main()
