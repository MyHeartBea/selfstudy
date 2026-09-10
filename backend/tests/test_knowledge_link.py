"""知识点 ↔ 错题双向链接的回归测试。

背景：134 个知识点里只有 83 个能和错题标签同名对上，所以链接要支持
「名称直接命中」与「靠 related_tags 兜底命中」两条路径，并如实报告命中方式。
"""

import sqlite3
import unittest

from app.models.tables import TABLES_DDL
from app.services import knowledge_service


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.execute("INSERT INTO subjects (id, name) VALUES (1, '测试科目')")
    conn.commit()
    return conn


def add_mistake(conn, question: str, tags, wrong=0, mastery=0, review_count=0) -> int:
    import json

    cur = conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, correct_answer, "
        "analysis, difficulty, difficulty_points, knowledge_tags, source_type, "
        "mastery_level, review_count, wrong_count) "
        "VALUES (1, 'choice', ?, 'A', '解析', 3, '难点', ?, 'other', ?, ?, ?)",
        (question, json.dumps(tags, ensure_ascii=False), mastery, review_count, wrong),
    )
    mid = cur.lastrowid
    for t in tags:
        conn.execute(
            "INSERT INTO mistake_tag_map (mistake_id, tag) VALUES (?, ?)", (mid, t)
        )
    conn.commit()
    return mid


class KnowledgeLinkTest(unittest.TestCase):
    def test_direct_tag_name_match(self):
        conn = make_conn()
        add_mistake(conn, "题1", ["特征值与特征向量"], wrong=2, mastery=0)
        add_mistake(conn, "题2", ["特征值与特征向量"], wrong=1, mastery=1)
        add_mistake(conn, "别的题", ["导数"])

        res = knowledge_service.get_knowledge_mistakes(conn, "特征值与特征向量")
        self.assertEqual(res["matched_by"], "tag_name")
        self.assertEqual(res["total"], 2)
        self.assertEqual(len(res["items"]), 2)
        self.assertEqual(res["stats"]["wrong_total"], 3)
        # 错得多的排前面
        self.assertEqual(res["items"][0]["question"], "题1")

    def test_related_tags_fallback_when_name_not_matched(self):
        """知识点名对不上错题标签时，用 related_tags 兜底并标明 matched_by。"""
        conn = make_conn()
        add_mistake(conn, "题A", ["虚拟化技术"])
        add_mistake(conn, "题B", ["特权指令"])

        res = knowledge_service.get_knowledge_mistakes(
            conn, "虚拟机管理程序", 50, ["虚拟化技术", "特权指令", "操作系统"]
        )
        self.assertEqual(res["matched_by"], "related_tags")
        self.assertEqual(res["total"], 2)
        # matched_tags = 查询用到的标签；hit_tags = 真正挂有错题的标签
        self.assertIn("操作系统", res["matched_tags"])
        self.assertNotIn("操作系统", res["hit_tags"], "没有对应错题的标签不该算命中")
        self.assertEqual(sorted(res["hit_tags"]), ["特权指令", "虚拟化技术"])

    def test_name_match_wins_over_related_tags(self):
        conn = make_conn()
        add_mistake(conn, "同名题", ["等价无穷小"])
        add_mistake(conn, "关联题", ["极限"])

        res = knowledge_service.get_knowledge_mistakes(conn, "等价无穷小", 50, ["极限"])
        self.assertEqual(res["matched_by"], "tag_name")
        self.assertEqual(res["matched_tags"], ["等价无穷小"])
        self.assertEqual([i["question"] for i in res["items"]], ["同名题"])

    def test_no_link_reports_none_with_stable_shape(self):
        """没有关联错题时也必须返回完整字段（前端直接读 matched_by/total/stats）。"""
        conn = make_conn()
        res = knowledge_service.get_knowledge_mistakes(conn, "不存在的知识点", 50, ["也没有"])
        self.assertEqual(res["matched_by"], "none")
        self.assertEqual(res["total"], 0)
        self.assertEqual(res["items"], [])
        for key in ("avg_mastery", "wrong_total", "review_total", "due_now", "never_reviewed", "shown"):
            self.assertIn(key, res["stats"], f"stats 缺少 {key}")

    def test_empty_tag_is_safe(self):
        conn = make_conn()
        res = knowledge_service.get_knowledge_mistakes(conn, "", 50, None)
        self.assertEqual(res["matched_by"], "none")
        self.assertEqual(res["total"], 0)

    def test_limit_respected(self):
        conn = make_conn()
        for i in range(5):
            add_mistake(conn, f"题{i}", ["极限"], wrong=i)
        res = knowledge_service.get_knowledge_mistakes(conn, "极限", 3)
        self.assertEqual(res["total"], 5, "total 是总数")
        self.assertEqual(len(res["items"]), 3, "items 受 limit 限制")
        self.assertEqual(res["stats"]["shown"], 3)

    def test_due_and_never_reviewed_counted(self):
        conn = make_conn()
        # 一题从未复习（next_review_at 为空）
        add_mistake(conn, "新题", ["导数"], review_count=0)
        # 一题已排到未来
        conn.execute(
            "UPDATE mistakes SET next_review_at = datetime('now', '+30 days'), review_count = 2 "
            "WHERE question = '新题'"
        )
        add_mistake(conn, "另一题", ["导数"], review_count=0)
        res = knowledge_service.get_knowledge_mistakes(conn, "导数")
        self.assertEqual(res["total"], 2)
        self.assertGreaterEqual(res["stats"]["due_now"], 1)
        self.assertGreaterEqual(res["stats"]["never_reviewed"], 1)


if __name__ == "__main__":
    unittest.main()
