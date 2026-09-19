"""v11 索引补齐的回归：索引必须**存在**且**真的被查询计划用上**。

只断言"索引名字在 sqlite_master 里"是不够的 —— 列序写反（(id, mistake_id) 这种）
一样能建成功，但 `WHERE mistake_id = ?` 用不上它，计划里照样是全表扫描。
所以每条都用 EXPLAIN QUERY PLAN 验一次，用的正是服务层/路由里那句原文。
"""

import sqlite3
import unittest

from app.database import migrate_database
from app.models.tables import TABLES_DDL

NEW_INDEXES = (
    "idx_solution_grades_mistake",
    "idx_vocab_created",
    "idx_mock_records_created",
    "idx_exam_papers_source_year",
    "idx_essay_records_kind_id",
)


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TABLES_DDL)
    conn.commit()
    return conn


def index_names(conn) -> set:
    return {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    }


def plan(conn, sql, params=()) -> str:
    return " ".join(
        row["detail"] for row in conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    )


class IndexDefinitionTest(unittest.TestCase):
    def test_new_indexes_exist(self):
        names = index_names(make_conn())
        for name in NEW_INDEXES:
            self.assertIn(name, names)

    def test_dropped_single_column_index_stays_gone(self):
        """建表脚本每次启动都跑：DROP 之后不许被别处再建回来。"""
        conn = make_conn()
        migrate_database(conn)
        self.assertNotIn("idx_essay_records_kind", index_names(conn))

    def test_idempotent_on_second_boot(self):
        conn = make_conn()
        migrate_database(conn)
        first = index_names(conn)
        conn.executescript(TABLES_DDL)
        migrate_database(conn)
        self.assertEqual(first, index_names(conn))


class QueryPlanTest(unittest.TestCase):
    """计划断言必须**在有成百上千行的量级**上做。

    踩过一次：表里只塞 1~3 行时，SQLite 的成本模型认定"扫这张小表"更便宜，
    于是即便索引建对了、查询写得也对，EXPLAIN 仍输出 SCAN —— 测试红了，但红的是测试。
    """

    ROWS = 400

    def setUp(self):
        self.conn = make_conn()
        self.conn.execute("INSERT INTO subjects (id, name) VALUES (1, '数学')")
        for i in range(1, self.ROWS + 1):
            self.conn.execute(
                "INSERT INTO mistakes (id, subject_id, question) VALUES (?, 1, 't')", (i,)
            )
            self.conn.execute(
                "INSERT INTO exam_papers (source_path, year, status) VALUES (?, ?, 'done')",
                (f"paper-{i}.pdf", f"20{10 + i % 16}"),
            )
            self.conn.execute(
                "INSERT INTO solution_grades (mistake_id, user_answer, score) VALUES (?, 'x', ?)",
                (i, 50 + i % 40),
            )
            self.conn.execute(
                "INSERT INTO mock_records (created_at, score) VALUES (?, ?)",
                (f"2026-01-{i % 28 + 1:02d} 00:00:00", i),
            )
            self.conn.execute(
                "INSERT INTO vocab_items (word, meaning, created_at) VALUES (?, 'm', ?)",
                (f"w{i}", f"2026-0{1 + i % 9}-0{i % 28 + 1:02d} 00:00:00"),
            )
            self.conn.execute(
                "INSERT INTO essay_records (kind, score, created_at) VALUES (?, ?, ?)",
                ("e2_long" if i % 2 else "e1_short", 10 + i % 5, f"2026-01-{i % 28 + 1:02d}"),
            )
        self.conn.commit()
        self.conn.execute("ANALYZE")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_last_grade_lookup(self):
        """mistake_service.get_mistake 取 last_grade 的原句。"""
        detail = plan(
            self.conn,
            "SELECT score FROM solution_grades WHERE mistake_id = ? ORDER BY id DESC LIMIT 1",
            (7,),
        )
        self.assertIn("idx_solution_grades_mistake", detail)
        self.assertNotIn("SCAN solution_grades", detail)

    def test_grade_delete_by_mistake(self):
        detail = plan(
            self.conn,
            f"DELETE FROM solution_grades WHERE mistake_id IN ({self.ROWS + 1}, {self.ROWS + 2})",
        )
        self.assertIn("idx_solution_grades_mistake", detail)

    def test_vocab_default_sort(self):
        detail = plan(
            self.conn,
            "SELECT id FROM vocab_items ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 0",
        )
        self.assertIn("idx_vocab_created", detail)
        self.assertNotIn("USE TEMP B-TREE", detail)

    def test_mock_list_sort(self):
        detail = plan(
            self.conn,
            "SELECT * FROM mock_records ORDER BY created_at DESC, id DESC LIMIT 20",
        )
        self.assertIn("idx_mock_records_created", detail)

    def test_paper_dedupe_lookup(self):
        """routers/papers.create_paper 的幂等查重原句。"""
        detail = plan(
            self.conn,
            "SELECT * FROM exam_papers WHERE source_path = ? AND year = ?",
            (f"paper-{self.ROWS}.pdf", f"20{10 + self.ROWS % 16}"),
        )
        self.assertIn("idx_exam_papers_source_year", detail)

    def test_essay_kind_filter_and_sort(self):
        detail = plan(
            self.conn,
            "SELECT * FROM essay_records WHERE kind = ? ORDER BY id DESC LIMIT 15 OFFSET 0",
            ("e2_long",),
        )
        self.assertIn("idx_essay_records_kind_id", detail)
        self.assertNotIn("USE TEMP B-TREE", detail)


class TagMapPrimaryKeyTest(unittest.TestCase):
    """mistake_tag_map 不另建索引：(mistake_id, tag) 主键就是 best index。

    记下来是为了下次体检别再把它当成"缺索引"重复报一遍。
    """

    def test_mistake_id_lookup_uses_pk(self):
        conn = make_conn()
        conn.execute("INSERT INTO mistakes (id, subject_id, question) VALUES (1, 1, 't')")
        conn.execute("INSERT INTO mistake_tag_map (mistake_id, tag) VALUES (1, '微分方程')")
        conn.commit()
        detail = plan(conn, "DELETE FROM mistake_tag_map WHERE mistake_id = 1")
        self.assertNotIn("SCAN mistake_tag_map", detail)
        conn.close()


if __name__ == "__main__":
    unittest.main()
