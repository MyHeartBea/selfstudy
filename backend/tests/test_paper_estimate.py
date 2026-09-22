"""导入前账单（/api/papers/estimate）的回归测试。

estimate_import 的数字必须诚实：扫描版、详解册、依赖缺失都要在 warnings 里明说，
宁可"估不了"也不给假数字。这里打桩 _probe_file（本地探针）来钉账单算术，
不依赖 pypdf/python-docx（CI 也没有），探针本身的真实行为由流水线侧验证。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import exam_paper_service as eps

client = TestClient(app)


def _make_root(tmp: str, names: list) -> Path:
    root = Path(tmp)
    for n in names:
        (root / n).write_bytes(b"x")
    return root


class EstimateBillTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _patch_root(self, names):
        root = _make_root(self._tmp.name, names)
        p = patch.object(eps, "papers_root", lambda: root)
        p.start()
        self.addCleanup(p.stop)
        return root

    def _patch_probe(self, source, answer=None):
        def fake_probe(path, kind):
            return source if kind == "source" else (answer or source)

        p = patch.object(eps, "_probe_file", side_effect=fake_probe)
        p.start()
        self.addCleanup(p.stop)

    def test_text_pdf_bill(self):
        """文本层可用：chunks = 字数/9000 向上取整，答案文件 +1 次调用。"""
        self._patch_root(["2024年数学二真题.pdf", "2024年数学二真题答案速查.pdf"])
        self._patch_probe({"pages": 4, "chars": 95000, "usable": True, "ok": True})
        r = eps.estimate_import("2024年数学二真题.pdf", "2024年数学二真题答案速查.pdf")
        self.assertEqual(r["chunks"], 11)  # ceil(95000/9000)
        self.assertEqual(r["ai_calls"], 12)
        self.assertEqual(r["minutes"], 33)
        self.assertFalse(r["scanned"])
        self.assertFalse(r["high_risk"])
        self.assertTrue(any("调用次数偏多" in w for w in r["warnings"]))

    def test_scanned_pdf_is_high_risk(self):
        """扫描版：逐页调用、high_risk、上限为 PDF_OCR_PAGES。"""
        self._patch_root(["2024年数学二真题.pdf"])
        self._patch_probe({"pages": 40, "chars": 300, "usable": False, "ok": True})
        with patch.object(eps.settings, "PDF_OCR_PAGES", 60):
            r = eps.estimate_import("2024年数学二真题.pdf")
        self.assertTrue(r["scanned"])
        self.assertTrue(r["high_risk"])
        self.assertEqual(r["ai_calls"], 40)
        self.assertTrue(any("扫描版" in w for w in r["warnings"]))

    def test_scanned_pages_capped(self):
        self._patch_root(["2024年数学二真题.pdf"])
        self._patch_probe({"pages": 120, "chars": 300, "usable": False, "ok": True})
        with patch.object(eps.settings, "PDF_OCR_PAGES", 60):
            r = eps.estimate_import("2024年数学二真题.pdf")
        self.assertEqual(r["ai_calls"], 60)

    def test_scanned_answer_file_adds_ocr_calls(self):
        """答案册也是扫描版：流水线会对它整册 OCR，账单要加这笔。"""
        self._patch_root(["2024年数学二真题.pdf", "2024年数学二真题详解.pdf"])
        self._patch_probe(
            {"pages": 4, "chars": 50000, "usable": True, "ok": True},
            answer={"pages": 30, "chars": 100, "usable": False, "ok": True},
        )
        r = eps.estimate_import("2024年数学二真题.pdf", "2024年数学二真题详解.pdf")
        self.assertEqual(r["ai_calls"], 7 + 30)  # 拆题 6 段 + 答案匹配 1 次 + 答案册 OCR 30 页
        self.assertTrue(r["high_risk"])
        self.assertTrue(any("答案册" in w for w in r["warnings"]))

    def test_mixed_file_warns(self):
        """详解册/合卷：账单上明确劝退，推荐纯试题册。"""
        self._patch_root(["2024年数学二真题解析.pdf"])
        self._patch_probe({"pages": 60, "chars": 200000, "usable": True, "ok": True})
        r = eps.estimate_import("2024年数学二真题解析.pdf")
        self.assertTrue(any("纯试题册" in w for w in r["warnings"]))
        self.assertEqual(r["chunks"], 23)  # ceil(200000/9000) 调用成倍多

    def test_missing_source_not_estimable(self):
        self._patch_root([])
        r = eps.estimate_import("不存在.pdf")
        self.assertFalse(r["estimable"])
        self.assertTrue(r["warnings"])

    def test_missing_answer_warns(self):
        self._patch_root(["2024年数学二真题.pdf"])
        self._patch_probe({"pages": 2, "chars": 5000, "usable": True, "ok": True})
        r = eps.estimate_import("2024年数学二真题.pdf", "没有这份答案.pdf")
        self.assertTrue(any("答案文件不存在" in w for w in r["warnings"]))


class EstimateRouteTest(unittest.TestCase):
    def test_rejects_path_escape(self):
        r = client.get("/api/papers/estimate", params={"source_path": "../backend/main.py"})
        self.assertEqual(r.status_code, 400)

    def test_rejects_absolute_path(self):
        r = client.get("/api/papers/estimate", params={"source_path": "C:/Windows/win.ini"})
        self.assertEqual(r.status_code, 400)
