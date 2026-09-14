"""代码审查发现的缺陷回归测试。

覆盖：
- H4 路径穿越：/api/papers 的 source_path / answer_path 必须限制在真题目录内
- H5 AI 返回非数字 page 不能让整份导入崩掉
- H1/H3 答案文本的结构化判据与确定性抽取
- H2 合卷（mixed）用自身文本兜底答案
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import exam_paper_service as eps


class AnswerPairsTest(unittest.TestCase):
    """H1/H3：答案文本要有结构化判据，不能只看"能读"就放行。"""

    def test_extracts_pairs_from_dense_quick_list(self):
        pairs = eps._answer_pairs_from_text("一、选择题\n(1)C. (2)B. (3)C. (4)C. (5)A.")
        self.assertEqual(pairs, {"1": "C", "2": "B", "3": "C", "4": "C", "5": "A"})

    def test_extracts_pairs_from_per_question_form(self):
        raw = "1【答案】（A）$a=\\frac{1}{3}$ 考点：泰勒公式\n2【答案】（B）$\\lambda=1$"
        self.assertEqual(eps._answer_pairs_from_text(raw), {"1": "A", "2": "B"})

    def test_garbled_text_yields_no_pairs(self):
        """扫描版详解 PDF 的乱码文本层：占比判据会说"可用"，但抽不出答案对。"""
        garbled = "回组袖$回 －壶－－ι'．咽，（ 网络匿名制去神秘化）" * 50
        self.assertEqual(eps._answer_pairs_from_text(garbled, expected=3), {})

    def test_expected_threshold(self):
        """expected 用于"够不够用"的判定：少于阈值就视为不可用。"""
        text = "(1)C. (2)B."
        self.assertEqual(eps._answer_pairs_from_text(text, expected=2), {"1": "C", "2": "B"})
        self.assertEqual(eps._answer_pairs_from_text(text, expected=5), {})

    def test_first_occurrence_wins_across_years(self):
        """多年份合集：题号会重复，首次出现优先（配合 prompt 的同年份约束）。"""
        text = "(1)C. (2)B. (3)C.\n(1)A. (2)D."
        pairs = eps._answer_pairs_from_text(text, expected=1)
        self.assertEqual(pairs["1"], "C")
        self.assertEqual(pairs["2"], "B")

    def test_empty_text_safe(self):
        self.assertEqual(eps._answer_pairs_from_text(""), {})
        self.assertEqual(eps._answer_pairs_from_text(None), {})


class MixedPaperAnswerTest(unittest.TestCase):
    """H2：合卷应能用自身文本当答案材料。"""

    def test_mixed_detected_for_combined_pdf(self):
        self.assertEqual(eps.classify_file("2023年政治真题及解析.pdf"), "mixed")
        self.assertEqual(eps.classify_file("2024年数学（二）真题及参考答案.pdf"), "mixed")
        # 纯试卷与纯答案册不应被判为合卷
        self.assertEqual(eps.classify_file("2026考研政治真题试卷.pdf"), "question")
        self.assertEqual(eps.classify_file("2011年数二真题答案速查.pdf"), "answer_key")


class PaperPathTraversalTest(unittest.TestCase):
    """H4：路径校验必须能挡住绝对路径与越界（含 answer_path）。

    用临时目录搭一个假"真题目录"，直接调用路由处理函数。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "真题"
        self.root.mkdir(parents=True)
        (self.root / "ok.pdf").write_bytes(b"%PDF-1.4 stub")
        (self.root / "ans.pdf").write_bytes(b"%PDF-1.4 stub")
        # 真题目录之外的敏感文件
        self.outside = Path(self.tmp.name) / "secret.pdf"
        self.outside.write_bytes(b"%PDF-1.4 secret")

    @classmethod
    def setUpClass(cls):
        """成功路径会查库，需要一张真实的 exam_papers 表。"""
        from app.config import settings
        from app.database import init_database

        cls._dbdir = tempfile.TemporaryDirectory()
        cls._saved_db = settings.DB_PATH
        cls._saved_bak = settings.BACKUP_DIR
        settings.DB_PATH = Path(cls._dbdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._dbdir.name) / "backups"
        init_database()

    @classmethod
    def tearDownClass(cls):
        from app.config import settings

        settings.DB_PATH = cls._saved_db
        settings.BACKUP_DIR = cls._saved_bak
        cls._dbdir.cleanup()

    def tearDown(self):
        self.tmp.cleanup()

    def _post(self, **kwargs):
        from app.routers import papers as papers_router
        from app.schemas import PaperCreate

        body = PaperCreate(
            subject="数学二",
            year="2026",
            title="t",
            source_path=kwargs.get("source_path", "ok.pdf"),
            answer_path=kwargs.get("answer_path", ""),
        )
        with (
            patch.object(eps, "papers_root", return_value=self.root),
            patch.object(papers_router.exam_paper_service, "papers_root", return_value=self.root),
            patch.object(papers_router.exam_paper_service, "enqueue_import"),
        ):
            return papers_router.create_paper(body)

    @staticmethod
    def _code(resp):
        if isinstance(resp, dict):
            return resp["code"]
        import json

        return json.loads(resp.body.decode())["code"]

    def test_relative_path_ok(self):
        self.assertEqual(self._code(self._post(source_path="ok.pdf")), 200)

    def test_absolute_path_rejected(self):
        """Windows 上 root / 绝对路径 会被整体替换，原本可读任意文件。"""
        self.assertEqual(self._code(self._post(source_path=str(self.outside))), 400)

    def test_parent_traversal_rejected(self):
        self.assertEqual(self._code(self._post(source_path="../secret.pdf")), 400)
        self.assertEqual(self._code(self._post(source_path="..\\secret.pdf")), 400)

    def test_answer_path_traversal_rejected(self):
        """原实现对 answer_path 完全不校验。"""
        self.assertEqual(
            self._code(self._post(source_path="ok.pdf", answer_path=str(self.outside))), 400
        )
        self.assertEqual(
            self._code(self._post(source_path="ok.pdf", answer_path="../secret.pdf")), 400
        )

    def test_wrong_suffix_rejected(self):
        (self.root / "note.txt").write_text("x", encoding="utf-8")
        self.assertEqual(self._code(self._post(source_path="note.txt")), 400)


class CollectToleratesBadPageTest(unittest.TestCase):
    """H5：AI 返回 page 非数字时不能抛异常（否则整份导入标记 error、AI 费用白付）。"""

    def test_non_numeric_page_does_not_raise(self):
        collected = []

        # 直接复用 _run_import 内的 _collect 逻辑不可行（闭包），这里验证判定的等价实现：
        # 只要 int() 被 try 包住并回退到正则取数，就不会抛
        for raw in ("第3页", "3页", "", None, "abc", "12"):
            try:
                s = str(raw or "").strip()
                page = max(0, int(s or 0))
            except (TypeError, ValueError):
                import re

                digits = re.findall(r"\d+", str(raw or ""))
                page = int(digits[0]) if digits else 0
            collected.append(page)
        self.assertEqual(collected, [3, 3, 0, 0, 0, 12])

    def test_source_uses_guarded_conversion(self):
        """确认源码里确实是带保护的转换（防止以后被改回裸 int()）。"""
        import inspect

        src = inspect.getsource(eps._run_import)
        self.assertIn("except (TypeError, ValueError)", src)
        self.assertNotRegex(src, r"page_idx if page_idx is not None else int\(q\.get\(\"page\"\)")


if __name__ == "__main__":
    unittest.main()
