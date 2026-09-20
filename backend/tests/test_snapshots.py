"""整库回滚（N11）：快照来源标记、回滚可用性校验、反悔点、确认口径、坏快照不动数据。

这批用例钉的全是"一步毁掉当前数据"的那条路径，所以重点不在"回滚能不能成功"，
而在**它该拒绝的时候必须拒绝，且拒绝时一个字都不改**。
`restore_snapshot()` 里那句 `if not path.exists()` 复查对应的是保留份数清理：
用户挑中最旧那一份时，打反悔点的那一步会先把目标删掉 —— 少了复查，
`sqlite3.connect()` 会凭空建一个空库并把当前数据覆盖成空白。
"""

import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.database import (
    get_connection,
    init_database,
    list_snapshots,
    restore_snapshot,
    snapshot_database,
    snapshot_label,
)
from app.main import app

OLD_NAME = "kaoyan_mistakes_20200101_000000_old.db"


class SnapshotRestoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        # 每条用例都要独立的库 + 独立的备份目录（回滚会在备份目录里造文件）
        self._orig_db = settings.DB_PATH
        self._orig_backup = settings.BACKUP_DIR
        self.addCleanup(self._restore_settings)
        settings.DB_PATH = root / "test.db"
        settings.BACKUP_DIR = root / "backups"
        init_database()
        self.client = TestClient(app)
        self.conn = get_connection()
        self.addCleanup(self.conn.close)

    def _restore_settings(self):
        settings.DB_PATH = self._orig_db
        settings.BACKUP_DIR = self._orig_backup

    # —— 自己的小工具 ——
    def _add_mistake(self, question: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO mistakes (subject_id, question) VALUES (1, ?)", (question,)
        )
        self.conn.commit()
        return cur.lastrowid

    def _count(self, table: str = "mistakes") -> int:
        return self.conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    def _snapshot(self, label: str) -> str:
        name = snapshot_database(label)
        self.assertIsNotNone(name, "快照都没打出来，后面的断言没有意义")
        return name

    def _post_restore(self, name: str, confirm=None):
        return self.client.post(
            "/api/snapshots/restore",
            json={"name": name, "confirm": name if confirm is None else confirm},
        )

    # —— 1. 来源标记 ——
    def test_snapshot_label_reports_origin(self):
        self.assertEqual(snapshot_label("kaoyan_mistakes_20260101_090000.db"), "")
        self.assertEqual(snapshot_label("kaoyan_mistakes_20260101_090000_manual.db"), "manual")
        self.assertEqual(
            snapshot_label("kaoyan_mistakes_20260101_090000_before-import.db"), "before-import"
        )
        name = self._snapshot("before-import")
        listed = list_snapshots(20)
        self.assertEqual([s for s in listed if s["name"] == name][0]["label"], "before-import")

    # —— 2. 正常回滚 ——
    def test_restore_brings_data_back_and_keeps_a_safety_snapshot(self):
        mid = self._add_mistake("要求回滚的那道题")
        name = self._snapshot("unit-test")
        self.conn.execute("DELETE FROM mistakes WHERE id = ?", (mid,))
        self.conn.commit()
        self.assertEqual(self._count_of(mid), 0)

        res = self._post_restore(name)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()["data"]
        self.assertEqual(data["name"], name)
        self.assertTrue(data["safety_snapshot"].endswith("before-restore.db"))
        self.assertEqual(data["tables_after"]["mistakes"], data["tables_before"]["mistakes"] + 1)
        self.assertIsNotNone(
            self.conn.execute("SELECT 1 FROM mistakes WHERE id = ?", (mid,)).fetchone()
        )
        # 文案必须说清图片不在回滚范围内（备份目录里从来没有图片，删掉的图找不回来）
        self.assertIn("图片", res.json()["message"])

    def _count_of(self, mistake_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) AS n FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()["n"]

    # —— 3. 确认口径 ——
    def test_restore_requires_exact_confirm(self):
        name = self._snapshot("unit-test")
        self._add_mistake("确认后才会被覆盖掉的新题")
        before = self._count()

        res = self._post_restore(name, confirm=name[:-4])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self._count(), before, "确认不一致时不能动任何数据")
        # 也不能顺手把反悔点写进备份目录（那会让快照列表多出一条没发生过的记录）
        self.assertFalse(
            any(p.name.endswith("before-restore.db") for p in settings.BACKUP_DIR.glob("*.db"))
        )

    # —— 4. 名字与路径 ——
    def test_restore_rejects_foreign_or_traversing_names(self):
        for bad in (
            "../../../etc/passwd.db",
            "kaoyan_mistakes_20260101_090000.db/../../secret.db",
            "not-a-snapshot.db",
            "kaoyan_mistakes_2026_01_01.db",
            # 标签上限 40 字符：这份的标签有 41 个字符，不属于本系统写出的任何名字
            f"kaoyan_mistakes_20260101_090000_{'x' * 41}.db",
            "",
        ):
            with self.subTest(bad=bad):
                before = self._count()
                res = self._post_restore(bad)
                self.assertIn(res.status_code, (400, 422), f"{bad} -> {res.status_code}")
                self.assertEqual(self._count(), before, f"{bad} 被拒后仍改动了数据")
                self.assertFalse(
                    any(
                        p.name.endswith("before-restore.db")
                        for p in settings.BACKUP_DIR.glob("*.db")
                    ),
                    f"{bad} 被拒却留下了反悔点",
                )

    def test_restore_missing_snapshot_is_404(self):
        res = self._post_restore("kaoyan_mistakes_19990101_000000.db")
        self.assertEqual(res.status_code, 404)

    # —— 5. 坏快照必须被挡住 ——
    def test_restore_refuses_file_that_is_not_a_database(self):
        settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        (settings.BACKUP_DIR / "kaoyan_mistakes_19990101_000000.db").write_bytes(b"0" * 4096)
        before = self._count()

        res = self._post_restore("kaoyan_mistakes_19990101_000000.db")
        self.assertEqual(res.status_code, 409, res.text)
        self.assertEqual(self._count(), before)

    def test_restore_refuses_database_without_mistakes_table(self):
        settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        fake = settings.BACKUP_DIR / "kaoyan_mistakes_19990101_000001.db"
        other = sqlite3.connect(fake)
        other.execute("CREATE TABLE something_else (id INTEGER)")
        other.commit()
        other.close()
        before = self._count()

        with self.assertRaises(RuntimeError):
            restore_snapshot(fake.name)
        self.assertEqual(self._count(), before)

    # —— 6. 没有反悔点就不许覆盖 ——
    def test_restore_aborts_when_safety_snapshot_fails(self):
        name = self._snapshot("unit-test")
        self._add_mistake("快照失败时这道题必须还在")
        before = self._count()

        with patch("app.database.snapshot_database", return_value=None):
            res = self._post_restore(name)
        self.assertEqual(res.status_code, 409)
        self.assertIn("快照失败", res.json()["message"])
        self.assertEqual(self._count(), before)

    # —— 7. 保留份数清理不许把目标删掉 ——
    def test_restore_refuses_snapshot_pruned_by_retention_limit(self):
        """打反悔点会按 MAX_BACKUPS 清掉最旧的一份；若目标正是那一份，必须中止而不是清空当前库。"""
        settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(settings.DB_PATH, settings.BACKUP_DIR / OLD_NAME)
        self._add_mistake("这份题不能被清空")
        before = self._count()

        with patch.object(settings, "MAX_BACKUPS", 1):
            with self.assertRaises(RuntimeError) as ctx:
                restore_snapshot(OLD_NAME)
        self.assertIn("保留份数", str(ctx.exception))
        self.assertEqual(self._count(), before)
        # 反悔点仍然留下了（回滚没做成，但那一步的现场值得保留）
        self.assertTrue(
            any(p.name.endswith("before-restore.db") for p in settings.BACKUP_DIR.glob("*.db"))
        )

    # —— 8. 快照比代码旧时要把表补齐 ——
    def test_restore_reapplies_schema_newer_than_snapshot(self):
        """回滚到一份还没有 exam_papers 的旧快照后，/papers 不该因为缺表而 500。"""
        settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        old = settings.BACKUP_DIR / OLD_NAME
        shutil.copy(settings.DB_PATH, old)
        victim = sqlite3.connect(old)
        victim.execute("DROP TABLE exam_papers")
        victim.commit()
        victim.close()
        self.conn.execute("DROP TABLE exam_papers")
        self.conn.commit()

        restore_snapshot(OLD_NAME)

        self.assertIsNotNone(
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='exam_papers'"
            ).fetchone(),
            "回滚后没有重新套用 DDL，缺的表要等重启才回来",
        )


class SnapshotListContractTest(unittest.TestCase):
    """`GET /api/snapshots` 的形状是回滚页唯一的列表来源，字段名不能漂。"""

    def test_list_item_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_db, orig_backup = settings.DB_PATH, settings.BACKUP_DIR
            try:
                settings.DB_PATH = root / "t.db"
                settings.BACKUP_DIR = root / "backups"
                init_database()
                name = snapshot_database("manual")
                listed = TestClient(app).get("/api/snapshots").json()["data"]
            finally:
                settings.DB_PATH, settings.BACKUP_DIR = orig_db, orig_backup
        self.assertEqual(listed[0]["name"], name)
        self.assertEqual(set(listed[0]) >= {"name", "label", "size_kb", "created_at"}, True)


if __name__ == "__main__":
    unittest.main()
