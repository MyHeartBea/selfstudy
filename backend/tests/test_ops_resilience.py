"""运维韧性：真题导入队列的重启恢复、每日自动备份门控、日志轮转接线。

此前这三件事都是"单进程假设"的盲区：进程一死队列就没了、备份只在启动时打一份、
uvicorn access 日志把无轮转的重定向文件撑到无限大。
"""

import logging
import os
import tempfile
import time
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from app.config import settings
from app.database import (
    get_connection,
    init_database,
    last_daily_backup_age_hours,
    maybe_daily_backup,
)
from app.main import _setup_logging
from app.services import exam_paper_service as eps


class RecoverStuckPapersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()

    def _insert_paper(self, status):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO exam_papers (subject, year, title, source_path, status) "
                "VALUES (?, ?, ?, ?, ?)",
                ("数学二", 2020, f"卷-{status}", f"x/{status}.pdf", status),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def _status_of(self, paper_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT status, status_note FROM exam_papers WHERE id = ?", (paper_id,)
            ).fetchone()
            return row["status"], row["status_note"]
        finally:
            conn.close()

    def test_middle_states_requeued_and_marked_pending(self):
        stuck = self._insert_paper("extracting")
        with patch.object(eps, "enqueue_import") as enqueue:
            recovered = eps.recover_stuck_papers()
        self.assertEqual(recovered, [stuck])
        enqueue.assert_called_once_with(stuck)
        status, note = self._status_of(stuck)
        self.assertEqual(status, "pending")
        self.assertIn("重新排队", note)

    def test_terminal_states_not_touched(self):
        done_id = self._insert_paper("done")
        error_id = self._insert_paper("error")
        with patch.object(eps, "enqueue_import") as enqueue:
            recovered = eps.recover_stuck_papers()
        self.assertEqual(recovered, [])
        enqueue.assert_not_called()
        self.assertEqual(self._status_of(done_id)[0], "done")
        self.assertEqual(self._status_of(error_id)[0], "error")


class DailyBackupTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()

    def test_first_call_creates_daily_snapshot_then_skips(self):
        name = maybe_daily_backup()
        self.assertIsNotNone(name)
        self.assertTrue(name.endswith("_daily.db"))
        # 刚备份过：间隔内不重复打（否则 30 分钟一次的轮询会灌爆 BACKUP_DIR）
        self.assertIsNone(maybe_daily_backup())
        self.assertLess(last_daily_backup_age_hours(), 1.0)

    def test_stale_daily_snapshot_triggers_new_one(self):
        name = maybe_daily_backup()
        stale = time.time() - 48 * 3600
        os.utime(settings.BACKUP_DIR / name, (stale, stale))
        self.assertGreater(last_daily_backup_age_hours(), 24.0)
        fresh = maybe_daily_backup()
        self.assertIsNotNone(fresh)
        # 文件名时间戳粒度是 1 秒，同一秒内重打会得到同名文件（内容已被覆盖为
        # 新备份）——判定"确实重打了"要看 mtime 回到当下，而不是文件名变了
        self.assertLess(last_daily_backup_age_hours(), 1.0)


class LoggingSetupTest(unittest.TestCase):
    def test_root_uses_rotating_file_and_uvicorn_goes_file_only(self):
        _setup_logging()
        self.assertTrue(
            any(isinstance(h, RotatingFileHandler) for h in logging.getLogger().handlers)
        )
        # uvicorn 的 access 日志是 err.log 无限增长的元凶：必须收进文件、控制台只留 WARN+
        access = logging.getLogger("uvicorn.access")
        self.assertFalse(access.propagate)
        self.assertTrue(access.handlers)


if __name__ == "__main__":
    unittest.main()
