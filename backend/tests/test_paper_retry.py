"""真题导入：拆题检查点（断点续跑）+ 失败重试端点 + 删卷图示图清理。

背景：拆题一块失败整卷作废重烧 AI；检查点存 app_meta（免迁移），
重试时段数一致就跳过已成功段——已花的 AI 费用不白付。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_connection, init_database
from app.main import app
from app.services import exam_paper_service as eps

client = TestClient(app)


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        settings.DB_PATH = Path(self._tmp.name) / "test.db"
        settings.BACKUP_DIR = Path(self._tmp.name) / "backups"
        init_database()

    def _conn(self):
        return get_connection()

    def test_save_load_roundtrip(self):
        conn = self._conn()
        try:
            qs = [{"no": "1", "type": "choice", "question": "q1"}]
            eps._save_checkpoint(conn, 7, 3, qs, 9)
            cp = eps._load_checkpoint(conn, 7)
            self.assertEqual(cp["done"], 3)
            self.assertEqual(cp["chunks_total"], 9)
            self.assertEqual(cp["questions"], qs)
        finally:
            conn.close()

    def test_apply_skips_done_chunks(self):
        conn = self._conn()
        try:
            qs = [{"no": "1", "type": "choice"}, {"no": "2", "type": "fill"}]
            eps._save_checkpoint(conn, 7, 2, qs, 4)
            questions, seen = [], set()
            start = eps._apply_checkpoint(conn, 7, [c for c in range(4)], questions, seen)
            self.assertEqual(start, 2)
            self.assertEqual([q["no"] for q in questions], ["1", "2"])
            # 已灌回的题号进 seen，后续段同号题会被 _collect 去重
            self.assertIn("1|choice", seen)
        finally:
            conn.close()

    def test_apply_rejects_mismatched_chunk_total(self):
        """源文件换过/段数变了：检查点整体作废，从头拆（不拼半旧半新的题）。"""
        conn = self._conn()
        try:
            eps._save_checkpoint(conn, 7, 2, [{"no": "1", "type": "choice"}], 4)
            start = eps._apply_checkpoint(conn, 7, [0, 1, 2, 3, 4], [], set())
            self.assertEqual(start, 0)
        finally:
            conn.close()

    def test_apply_rejects_done_beyond_chunks(self):
        conn = self._conn()
        try:
            eps._save_checkpoint(conn, 7, 6, [{"no": "1", "type": "choice"}], 6)
            start = eps._apply_checkpoint(conn, 7, [0, 1, 2], [], set())
            self.assertEqual(start, 0)
        finally:
            conn.close()

    def test_clear(self):
        conn = self._conn()
        try:
            eps._save_checkpoint(conn, 7, 1, [{"no": "1", "type": "choice"}], 2)
            eps._clear_checkpoint(conn, 7)
            self.assertIsNone(eps._load_checkpoint(conn, 7))
        finally:
            conn.close()


class RetryPaperTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        cls._client_ctx = TestClient(app)
        cls._client_ctx.__enter__()
        cls.client = cls._client_ctx

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)
        cls._tmpdir.cleanup()

    def _insert(self, status):
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO exam_papers (subject, year, title, source_path, answer_path, "
                "status, created_at) VALUES ('数学二', '2024', 't', 'x.pdf', '', ?, 'now')",
                (status,),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def test_retry_error_paper(self):
        pid = self._insert("error")
        with patch.object(eps, "enqueue_import") as enq:
            r = self.client.post(f"/api/papers/{pid}/retry")
        self.assertEqual(r.status_code, 200)
        enq.assert_called_once_with(pid)
        conn = get_connection()
        try:
            row = conn.execute("SELECT status FROM exam_papers WHERE id = ?", (pid,)).fetchone()
            self.assertEqual(row["status"], "pending")
        finally:
            conn.close()

    def test_retry_rejects_non_error(self):
        pid = self._insert("done")
        r = self.client.post(f"/api/papers/{pid}/retry")
        self.assertEqual(r.status_code, 400)

    def test_retry_missing_404(self):
        r = self.client.post("/api/papers/99999/retry")
        self.assertEqual(r.status_code, 404)


class DeletePaperImagesTest(unittest.TestCase):
    def test_remove_paper_images_deletes_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        img_root = Path(tmp.name) / "exam_papers"
        d = img_root / "42"
        d.mkdir(parents=True)
        (d / "p0.webp").write_bytes(b"x")
        with patch.object(eps, "_IMAGE_ROOT", img_root):
            self.assertEqual(eps.remove_paper_images(42), 1)
            self.assertFalse(d.exists())
            self.assertEqual(eps.remove_paper_images(42), 0)


if __name__ == "__main__":
    unittest.main()
