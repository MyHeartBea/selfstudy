"""数据体检（N2）：引用归并、孤儿/缺图判定、缩略图跟随、keep_days 保护、只读端点契约。

`scan()` 的"当前时刻"由 `now` 注入，mtime 全部按它倒推 —— 否则用例会在真实日期
跨过保护期那天悄悄变红。
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_connection, init_database
from app.main import app
from app.services import integrity_service, mistake_service

DAY = 86400
# 固定的"现在"取**过去**的时刻：端点那条用例不注入 now（走真实时钟），
# 若 NOW 落在未来，文件的 mtime 就会比真实 cutoff 新 → 被算进"保护期内"，
# 同一份数据在单测里是孤儿、在端点用例里不是（实测就是这么红的）。
NOW = 1_700_000_000.0
OLD = NOW - 30 * DAY


def _write(images_dir: Path, rel: str, *, mtime: float = OLD, size: int = 10) -> Path:
    path = images_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


class IntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()

    def setUp(self):
        self._sub = tempfile.TemporaryDirectory()
        self.addCleanup(self._sub.cleanup)
        self.images = Path(self._sub.name) / "images"
        self.images.mkdir()
        patcher = patch.object(mistake_service, "IMAGE_DIR", self.images)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = get_connection()
        self.addCleanup(self.conn.close)
        # 临时库整个类共享，而这批用例**要写库**：不清干净的话上一条用例的引用
        # 会混进下一条的断言里（表现为"孤儿数对不上"这种莫名其妙红）。
        self.conn.execute("DELETE FROM exam_questions")
        self.conn.execute("DELETE FROM exam_papers")
        self.conn.execute("DELETE FROM mistakes")
        self.conn.commit()
        self.client = TestClient(app)

    # ---- 建数据 ----

    def _mistake(self, images, question="q"):
        raw = images if isinstance(images, str) else json.dumps(images)
        cur = self.conn.execute(
            "INSERT INTO mistakes (subject_id, question, images) VALUES (1, ?, ?)",
            (question, raw),
        )
        self.conn.commit()
        return cur.lastrowid

    def _diagram(self, value):
        paper = self.conn.execute(
            "INSERT INTO exam_papers (subject, year) VALUES ('数学一','2024')"
        )
        cur = self.conn.execute(
            "INSERT INTO exam_questions (paper_id, question, diagram_image) VALUES (?, 'q', ?)",
            (paper.lastrowid, value),
        )
        self.conn.commit()
        return cur.lastrowid

    def _write(self, rel, **kw):
        return _write(self.images, rel, **kw)

    def _scan(self, **kw):
        kw.setdefault("now", NOW)
        return integrity_service.scan(self.conn, self.images, **kw)

    # ---- 引用收集 ----

    def test_both_stored_shapes_merge_on_basename(self):
        """`images/a.png`（错题存的相对路径）与 `/images/exam_papers/1/p0.webp`（URL）要归并成一张。

        按整串比就会把同一张图看成两个，引用侧漏一条、文件侧多一条孤儿。
        """
        mid = self._mistake(["images/a.png"])
        qid = self._diagram("/images/exam_papers/1/p0.webp")
        refs, unparseable = integrity_service.image_references(self.conn)
        self.assertEqual(unparseable, 0)
        self.assertEqual(sorted(refs), ["a.png", "p0.webp"])
        self.assertEqual(refs["a.png"], [f"mistakes#{mid}"])
        self.assertEqual(refs["p0.webp"], [f"exam_questions#{qid}"])

    def test_unparseable_images_is_reported_not_silently_dropped(self):
        """坏 JSON 只能保守跳过，但必须回数：漏一条引用就等于把那张图判成孤儿。"""
        self._mistake("这不是JSON")
        refs, unparseable = integrity_service.image_references(self.conn)
        self.assertEqual(refs, {})
        self.assertEqual(unparseable, 1)

    def test_missing_table_does_not_crash_scan(self):
        """老库/临时库里没某张表时巡检要照常出结果，而不是整条 500。"""
        conn = get_connection()
        try:
            conn.execute("DROP TABLE exam_questions")
            conn.commit()
            self._write("a.png")
            report = integrity_service.scan(conn, self.images, now=NOW)
            self.assertEqual(report["orphan_total"], 1)
        finally:
            conn.close()
        init_database()  # 同库共享，补回来

    # ---- 孤儿与缺图 ----

    def test_orphan_and_missing_are_two_different_problems(self):
        """文件没人引用 = 孤儿；引用没有文件 = 缺图。两类必须分开报，修法也不同。"""
        self._write("orphan.png")
        self._mistake(["images/gone.png"])
        report = self._scan()
        self.assertEqual([o["rel"] for o in report["orphans"]], ["orphan.png"])
        self.assertEqual(report["missing_total"], 1)
        self.assertEqual(report["missing"][0]["name"], "gone.png")
        self.assertTrue(report["missing"][0]["refs"][0].startswith("mistakes#"))

    def test_exam_diagram_counts_as_a_reference(self):
        """只按 mistakes 判定的话，真题图示题的原图会被当成孤儿删掉（脚本原来的头号风险）。"""
        qid = self._diagram("/images/exam_papers/7/p3.webp")
        _write(self.images, "exam_papers/7/p3.webp")
        report = self._scan()
        self.assertEqual(report["orphan_total"], 0)
        self.assertEqual(report["missing_total"], 0)
        self.assertEqual(report["referenced"], 1)
        self.assertTrue(qid)

    def test_thumbnail_follows_its_main_image(self):
        """主图还在库里 → 它的缩略图不算孤儿；主图没了 → 缩略图跟着算（kind=thumb）。"""
        self._mistake(["images/keep.png"])
        _write(self.images, "keep.png")
        _write(self.images, "_thumbs/keep.webp")
        _write(self.images, "_thumbs/dead.webp")
        report = self._scan()
        self.assertEqual(
            [(o["rel"], o["kind"]) for o in report["orphans"]], [("_thumbs/dead.webp", "thumb")]
        )

    def test_recent_files_are_protected_and_counted(self):
        """后台拆题是"图先落盘、diagram_image 后写库"，中间那几秒不能被判成孤儿。"""
        _write(self.images, "fresh.png", mtime=NOW - 600)
        _write(self.images, "old.png", mtime=NOW - 3 * DAY)
        report = self._scan(keep_days=1)
        self.assertEqual([o["rel"] for o in report["orphans"]], ["old.png"])
        self.assertEqual(report["protected_recent"], 1)
        # 关掉保护期后它就该被列出来（口径确实由 keep_days 决定，不是硬编码）
        self.assertEqual(self._scan(keep_days=0)["orphan_total"], 2)

    def test_orphans_sorted_big_first_and_truncated_with_flag(self):
        for name, size in (("small.png", 100), ("huge.png", 5000), ("mid.png", 900)):
            _write(self.images, name, size=size)
        report = self._scan(limit=2)
        self.assertEqual([o["rel"] for o in report["orphans"]], ["huge.png", "mid.png"])
        self.assertEqual(report["orphan_total"], 3)
        self.assertTrue(report["orphan_truncated"])
        self.assertEqual(report["orphan_bytes"], 5000 + 900 + 100)

    def test_non_image_files_are_ignored(self):
        _write(self.images, "notes.txt")
        _write(self.images, "a.png.bak")
        self.assertEqual(self._scan()["orphan_total"], 0)

    def test_orphan_paths_matches_report_order(self):
        """脚本用的就是它，顺序要和页面上的清单一致（大的先删）。"""
        _write(self.images, "small.png", size=10)
        _write(self.images, "huge.png", size=1000)
        paths = integrity_service.orphan_paths(self.conn, self.images, keep_days=1)
        self.assertEqual([p.name for p in paths], ["huge.png", "small.png"])
        self.assertTrue(all(p.is_file() for p in paths))

    def test_scan_never_writes_to_disk(self):
        """只读是这整个功能的立足点：跑一遍体检后目录里的文件一张都不能少。"""
        self._mistake(["images/keep.png"])
        _write(self.images, "keep.png")
        _write(self.images, "orphan.png")
        before = sorted(p.name for p in self.images.rglob("*"))
        self._scan()
        integrity_service.scan(self.conn, self.images, now=NOW)
        self.assertEqual(before, sorted(p.name for p in self.images.rglob("*")))
        self.assertEqual(len(list(self.conn.execute("SELECT id FROM mistakes"))), 1)

    # ---- 端点 ----

    def test_integrity_endpoint_reports_without_deleting(self):
        _write(self.images, "orphan.png")
        res = self.client.get("/api/system/integrity")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["orphans"][0]["rel"], "orphan.png")
        self.assertTrue(data["images_dir_exists"])
        self.assertTrue((self.images / "orphan.png").is_file())  # 端点绝不删文件

    def test_endpoint_validates_params(self):
        for params in ({"limit": 0}, {"limit": 1001}, {"keep_days": -1}, {"keep_days": 31}):
            self.assertEqual(
                self.client.get("/api/system/integrity", params=params).status_code, 422
            )


if __name__ == "__main__":
    unittest.main()
