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

    def test_result_shape_matches_frontend_contract(self):
        make_tree(self.root, {"英语二/2013真题.pdf": "q", "英语二/2013答案速查.pdf": "a"})
        item = self.scan()[0]
        for key in ("rel_path", "name", "subject", "year", "answer_path", "size_kb"):
            self.assertIn(key, item, f"缺少前端依赖字段 {key}")


if __name__ == "__main__":
    unittest.main()
