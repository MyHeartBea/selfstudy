"""真题库扫描的回归测试：角色判定 / 去重合并 / 年份与科目识别。

修的是实测发现的问题：
- 150 份候选里 81 份"配不到答案"，其中 **52 份其实是题+答案合卷**（文件名含解析/详解），
  被 `_ANSWER_KEYS` 误判成「纯答卷」，于是既当不了试卷也配不到答案；
- 同一(科目,年份)有 3~5 份重复候选（真题 + 真题解析 + 答案速查），分不清该导哪个；
- 10 份年份识别为空（`26考研…`、`25数二…` 这类两位年缩写）；
- `2024年数学（一）真题及参考答案.pdf` 被识别成 数学二。
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import exam_paper_service as eps


class GuessYearTest(unittest.TestCase):
    def test_four_digit(self):
        self.assertEqual(eps.guess_year("2013年考研英语二真题解析.pdf"), "2013")
        self.assertEqual(eps.guess_year("2026考研英语二真题（PDF）"), "2026")

    def test_two_digit_shorthand(self):
        self.assertEqual(eps.guess_year("26考研英语二答案.pdf"), "2026")
        self.assertEqual(eps.guess_year("25考研政治真题.docx"), "2025")
        self.assertEqual(eps.guess_year("24考研政治选择题解析.pdf"), "2024")
        self.assertEqual(eps.guess_year("26数二参考答案.pdf"), "2026")

    def test_empty_when_no_year(self):
        self.assertEqual(eps.guess_year("考研英语（二）答题卡.pdf"), "")


class GuessSubjectTest(unittest.TestCase):
    def test_math_one_and_three_not_merged_into_two(self):
        self.assertEqual(eps.guess_subject("2024年数学（一）真题及参考答案.pdf"), "数学一")
        self.assertEqual(eps.guess_subject("2024年数学（三）真题及参考答案.pdf"), "数学三")
        self.assertEqual(eps.guess_subject("2011年数二真题答案速查.pdf"), "数学二")

    def test_other_subjects(self):
        self.assertEqual(eps.guess_subject("2013年考研英语二真题解析.pdf"), "英语二")
        self.assertEqual(eps.guess_subject("2025 年计算机统考真题.pdf"), "计算机408")
        self.assertEqual(eps.guess_subject("2025考研政治真题及解析.pdf"), "政治")

    def test_unknown(self):
        self.assertEqual(eps.guess_subject("随便一个文件.pdf"), "")


class ClassifyFileTest(unittest.TestCase):
    def test_mixed_paper_containing_questions_and_answers(self):
        """真题解析 = 题+答案合卷（不是纯答卷）。"""
        self.assertEqual(eps.classify_file("2013年考研英语二真题解析.pdf"), "mixed")
        self.assertEqual(eps.classify_file("2010年考研英语二真题解析.pdf"), "mixed")
        self.assertEqual(eps.classify_file("2020年考研数学二真题+解析.pdf"), "mixed")

    def test_answer_key(self):
        self.assertEqual(eps.classify_file("英语二真题答案速查2010-2024.pdf"), "answer_key")
        self.assertEqual(eps.classify_file("26数二参考答案.pdf"), "answer_key")
        self.assertEqual(eps.classify_file("24考研政治选择题解析.pdf"), "answer_key")
        # 「真题…答案速查」是速查册（题面在另一份文件里）
        self.assertEqual(eps.classify_file("2011年数二真题答案速查.pdf"), "answer_key")
    def test_paper_with_answers_is_mixed(self):
        """`真题及参考答案` 同时含题目与答案 → 合卷（不是纯答案册）。"""
        self.assertEqual(eps.classify_file("2024年数学（二）真题及参考答案.pdf"), "mixed")
        self.assertEqual(eps.classify_file("2013年考研英语二真题解析.pdf"), "mixed")

    def test_plain_question_paper(self):
        self.assertEqual(eps.classify_file("2022年考研政治真题.pdf"), "question")
        self.assertEqual(eps.classify_file("2026考研英语二试题.pdf"), "question")

    def test_unknown_other(self):
        self.assertEqual(eps.classify_file("考研英语（二）答题卡.pdf"), "other")


def make_tree(root: Path, files: dict):
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


class ScanFolderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def scan(self):
        with patch.object(eps, "papers_root", return_value=self.root):
            return eps.scan_folder()

    def test_dedupes_same_subject_and_year_into_one_candidate(self):
        """同年的 真题/真题解析/答案速查 必须合并成一条候选。"""
        make_tree(
            self.root,
            {
                "英语二/2013真题.pdf": "q",
                "英语二/2013年考研英语二真题解析.pdf": "mixed",
                "英语二/答案速查2013.pdf": "a",
            },
        )
        items = self.scan()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["subject"], "英语二")
        self.assertEqual(item["year"], "2013")
        self.assertEqual(len(item["sources"]), 3)
        # 主文件应选纯试卷，答案优先选答案册
        self.assertTrue(item["rel_path"].endswith("2013真题.pdf"))
        self.assertTrue(item["answer_path"])

    def test_mixed_only_year_is_still_importable(self):
        """只有合卷的年份也要能导入（旧实现会变成孤儿候选）。"""
        make_tree(self.root, {"政治/2023年政治真题及解析.pdf": "mixed"})
        items = self.scan()
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["mixed"])
        self.assertEqual(items[0]["year"], "2023")

    def test_answer_only_paper_is_not_a_candidate(self):
        """只有答案册、没有试卷的年份不产生候选。"""
        make_tree(self.root, {"英语二/答案速查2013.pdf": "a"})
        self.assertEqual(self.scan(), [])

    def test_math_one_and_two_are_separate_candidates(self):
        make_tree(
            self.root,
            {
                "数学/2024年数学（一）真题及参考答案.pdf": "m1",
                "数学/2024年数学（二）真题及参考答案.pdf": "m2",
            },
        )
        items = self.scan()
        subjects = sorted(i["subject"] for i in items)
        self.assertEqual(subjects, ["数学一", "数学二"], "数学一/二 不能合并")

    def test_two_digit_year_candidates(self):
        make_tree(self.root, {"政治/25考研政治真题.docx": "q", "政治/25考研政治真题答案.docx": "a"})
        items = self.scan()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["year"], "2025")
        self.assertTrue(items[0]["answer_path"])

    def test_ignores_temp_and_non_paper_files(self):
        make_tree(
            self.root,
            {"英语二/~$2013真题.pdf": "tmp", "英语二/说明.txt": "x", "英语二/2013真题.pdf": "q"},
        )
        items = self.scan()
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]["sources"]), 1)

    def test_prefers_real_answer_key_over_mixed_paper(self):
        """有真正的答案册时不要用「解析合卷」当答案来源（合卷里题面会干扰答案提取）。"""
        make_tree(
            self.root,
            {
                "英语二/2024年真题.docx": "q",
                "英语二/2024年真题解析.pdf": "mixed",
                "英语二/2024答案速查.pdf": "a",
            },
        )
        item = self.scan()[0]
        self.assertIn("答案速查", item["answer_path"])
        self.assertEqual(item["answer_kind"], "answer_key")

    def test_falls_back_to_mixed_when_no_answer_key(self):
        make_tree(
            self.root,
            {
                "英语二/2024年真题.docx": "q",
                "英语二/2024年真题解析.pdf": "mixed",
            },
        )
        item = self.scan()[0]
        self.assertIn("解析", item["answer_path"])
        self.assertEqual(item["answer_kind"], "mixed")

    def test_result_shape_matches_frontend_contract(self):
        make_tree(self.root, {"英语二/2013真题.pdf": "q", "英语二/2013答案速查.pdf": "a"})
        item = self.scan()[0]
        for key in ("rel_path", "name", "subject", "year", "answer_path", "size_kb"):
            self.assertIn(key, item, f"缺少前端依赖字段 {key}")


class NormalizeAnswerTextTest(unittest.TestCase):
    """答案册写法归一：实测这两种写法会让 10 道选择题只配到 1 道（还配错）。"""

    def test_dense_quick_list_is_split(self):
        from app.services.exam_paper_service import _normalize_answer_text

        raw = "一、选择题\n(1)C. (2)B. (3)C. (4)C. (5)A. (6)B. (7)D. (8)D."
        out = _normalize_answer_text(raw)
        for expect in ["1:C", "2:B", "3:C", "4:C", "5:A", "6:B", "7:D", "8:D"]:
            self.assertIn(expect, out, f"缺少 {expect}\n{out}")

    def test_per_question_with_explanation_keeps_letter_only(self):
        from app.services.exam_paper_service import _normalize_answer_text

        raw = (
            "1【答案】（A）$a=\\frac{1}{3},b=-1$ 考点：泰勒公式求参数\n"
            "2【答案】（B）$\\lambda=\\frac{2}{5}$ 考点：齐与非解的关系"
        )
        out = _normalize_answer_text(raw)
        self.assertIn("1:A", out)
        self.assertIn("2:B", out)
        # 选择题只留字母，考点文字不应参与匹配（避免干扰 AI）
        self.assertNotIn("泰勒公式", out)

    def test_per_question_fill_keeps_expression(self):
        from app.services.exam_paper_service import _normalize_answer_text

        out = _normalize_answer_text("11【答案】$0<p<2$ 考点：反常积分敛散性")
        self.assertIn("11:$0<p<2$", out)

    def test_already_normalized_untouched(self):
        from app.services.exam_paper_service import _normalize_answer_text

        raw = "1.A\n2:B\n3、C"
        self.assertEqual(_normalize_answer_text(raw), raw)

    def test_empty_safe(self):
        from app.services.exam_paper_service import _normalize_answer_text

        self.assertEqual(_normalize_answer_text(""), "")


class AnswerSectionMapTest(unittest.TestCase):
    def test_parses_question_number_ranges(self):
        from app.services.exam_paper_service import _answer_section_map

        exam = (
            "一、选择题:1～10 小题,每小题 5 分\n"
            "二、填空题 11-16题 每题5分\n"
            "三 解答题 17-22题 共70分"
        )
        m = _answer_section_map(exam)
        self.assertEqual(m.get("3"), "choice")
        self.assertEqual(m.get("11"), "fill")
        self.assertEqual(m.get("20"), "solution")

    def test_ignores_absurd_ranges(self):
        from app.services.exam_paper_service import _answer_section_map

        self.assertEqual(_answer_section_map("一、选择题 1～999 小题"), {})


class DocxImportBranchTest(unittest.TestCase):
    """docx 不能被当成"扫描版 PDF"（原实现无条件调 _pdf_text_layer，docx 得到空串）。"""

    def test_docx_uses_extract_text_not_pdf_text_layer(self):
        import inspect

        from app.services import exam_paper_service as svc

        src = inspect.getsource(svc._run_import)
        self.assertIn('suffix.lower() == ".docx"', src, "缺少 docx 专用分支")
        self.assertIn("page_pils: dict = {}", src, "page_pils 必须在分支前初始化")

    def test_docx_extraction_returns_text(self):
        """真实 docx（若样例存在）应能抽出文本，且不被判为扫描版。

        CI 不装 python-docx（也没有 D:\\km-v2\\真题 这个目录），因此这里要显式跳过，
        否则本地能过、CI 直接 ImportError（真实踩过）。
        """
        try:
            import docx  # noqa: F401
        except ImportError:
            self.skipTest("未安装 python-docx（CI 环境即如此）")

        sample = None
        papers_dir = Path(r"D:\km-v2\真题")
        if papers_dir.is_dir():
            for p in papers_dir.rglob("*.docx"):
                if not p.name.startswith("~$") and p.stat().st_size > 10000:
                    sample = p
                    break
        if sample is None:
            self.skipTest("真题目录里没有可用的 docx 样例")
        text = eps.extract_text(sample)
        self.assertGreater(len(text.strip()), 500, f"{sample.name} 抽出的文本过少")


if __name__ == "__main__":
    unittest.main()
