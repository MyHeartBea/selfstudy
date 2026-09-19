"""全站搜索 `GET /api/search`：分组形状、LIKE 转义、截断与空组行为。"""

import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.database import get_connection, init_database
from app.main import app
from app.services import search_service
from fastapi.testclient import TestClient


def _seed(conn):
    conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, analysis) "
        "VALUES (3,'choice','设函数 f(x)=x^2 在区间上连续，求极值','配平方差')"
    )
    conn.execute(
        "INSERT INTO mistakes (subject_id, question_type, question, analysis) "
        "VALUES (3,'choice','泰勒展开式 50% 收敛半径','莱布尼茨判别法')"
    )
    conn.execute(
        "INSERT INTO knowledge_base (tag_name, subject_id, summary) "
        "VALUES ('泰勒公式',3,'含麦克劳林展开与余项')"
    )
    conn.execute(
        "INSERT INTO formula_items (category, title, content) "
        "VALUES ('高等数学','泰勒公式','$f(x)=\\sum f^{(n)}(x_0)/n! (x-x_0)^n$')"
    )
    conn.execute(
        "INSERT INTO vocab_items (word, meaning, kind) VALUES ('algorithm','算法；运算法则','word')"
    )
    conn.execute(
        "INSERT INTO essay_records (kind, prompt_text, essay_text, score, max_score) "
        "VALUES ('e2_long','谈谈算法的重要性','As is vividly shown, algorithm matters.',12,15)"
    )
    conn.commit()


class SearchServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        settings.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        settings.BACKUP_DIR = Path(cls._tmpdir.name) / "backups"
        init_database()
        conn = get_connection()
        _seed(conn)
        conn.close()

    def tearDown(self):
        # 组内共享同一个临时库，但每条用例只读，不需要清库
        pass

    def _search(self, q, limit=5):
        conn = get_connection()
        try:
            return search_service.search_all(conn, q, limit)
        finally:
            conn.close()

    def _keys(self, result):
        return [g["key"] for g in result["groups"]]

    def test_hit_groups_shape_and_order(self):
        result = self._search("算法")
        self.assertEqual(result["q"], "算法")
        self.assertEqual(self._keys(result), ["vocab", "essays"])  # 按 GROUPS 顺序，不是按命中数
        vocab = result["groups"][0]
        self.assertEqual(vocab["label"], "生词")
        self.assertEqual(vocab["total"], 1)
        item = vocab["items"][0]
        self.assertEqual(item["title"], "algorithm")
        self.assertEqual(item["subtitle"], "算法；运算法则")
        self.assertEqual(item["meta"], "word")
        self.assertGreaterEqual(result["total"], 2)

    def test_empty_groups_omitted_and_blank_query_is_noop(self):
        self.assertEqual(self._search("zzz-不存在-anything")["groups"], [])
        self.assertEqual(self._search("")["total"], 0)
        self.assertEqual(self._search("   ")["groups"], [])

    def test_like_wildcards_are_literal_not_patterns(self):
        """搜 `50%` 只能命中含字面 "50%" 的那条；不转义会命中所有含 5 的内容。"""
        result = self._search("50%")
        self.assertEqual(self._keys(result), ["mistakes"])
        self.assertEqual(result["groups"][0]["total"], 1)
        self.assertIn("50%", result["groups"][0]["items"][0]["title"])
        # `%` / `_` 单独成串时必须按字面匹配，不能退化成"匹配一切"
        percent = self._search("%")
        for group in percent["groups"]:
            for item in group["items"]:
                self.assertIn("%", item["title"] + item["subtitle"])
        # "_a_b_" 当模式能匹配任意 "任意a任意b任意"（库里 LaTeX 下标一堆），
        # 当字面串则一条都不该命中
        self.assertEqual(self._search("_a_b_")["groups"], [])

    def test_limit_caps_items_but_total_counts_everything(self):
        result = self._search("的", limit=1)
        for group in result["groups"]:
            self.assertLessEqual(len(group["items"]), 1)
        self.assertGreaterEqual(result["total"], 2)

    def test_snippet_is_folded_and_centered_on_hit(self):
        long_text = "前言" * 60 + "\n第二行\n含关键词甲乙丙" + "x" * 200
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO knowledge_base (tag_name, subject_id, summary) VALUES ('长摘要考点',3,?)",
                (long_text,),
            )
            conn.commit()
        finally:
            conn.close()
        result = self._search("关键词甲乙丙")
        group = next(g for g in result["groups"] if g["key"] == "knowledge")
        hit = next(i for i in group["items"] if i["title"] == "长摘要考点")
        snippet = hit["subtitle"]
        self.assertNotIn("\n", snippet)  # 折叠成一行
        self.assertTrue(snippet.startswith("…"))
        self.assertIn("关键词甲乙丙", snippet)
        self.assertLess(len(snippet), 120)


class SearchApiTest(SearchServiceTest):
    """同一批用例走 HTTP：端点必须存在、信封一致、参数受约束。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = TestClient(app)

    def setUp(self):
        # 复用父类的用例时，把 _search 换成打 HTTP 的版本（形状断言两边共用）
        self._orig_search = self._search

        def via_http(q, limit=5):
            if not q.strip():
                # 端点层 min_length=1 会拒空串；服务层已单独测过
                return {"q": "", "limit": limit, "total": 0, "groups": []}
            r = self.client.get("/api/search", params={"q": q, "limit": limit})
            self.assertEqual(r.status_code, 200)
            body = r.json()
            self.assertEqual(body["code"], 200)
            return body["data"]

        self._search = via_http

    def test_missing_query_is_422_with_uniform_envelope(self):
        r = self.client.get("/api/search")
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("detail", r.json())

    def test_limit_out_of_range_is_rejected(self):
        for bad in (0, 21):
            self.assertEqual(
                self.client.get("/api/search", params={"q": "算法", "limit": bad}).status_code, 422
            )

    def test_http_envelope_matches_service_result(self):
        conn = get_connection()
        try:
            direct = search_service.search_all(conn, "算法", 5)
        finally:
            conn.close()
        r = self.client.get("/api/search", params={"q": "算法"})
        self.assertEqual(r.json()["data"], direct)


if __name__ == "__main__":
    unittest.main()
