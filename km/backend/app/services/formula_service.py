"""公式库相关业务逻辑。"""

import sqlite3
from typing import List, Optional


def list_formulas(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    """按分类或关键词查询公式条目。"""
    conditions = ["1 = 1"]
    params = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if search:
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    sql = (
        "SELECT * FROM formula_items WHERE "
        + " AND ".join(conditions)
        + " ORDER BY category, id DESC"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def create_formula(
    conn: sqlite3.Connection,
    category: str,
    title: str,
    content: str,
) -> Optional[dict]:
    """新增公式条目。"""
    cur = conn.execute(
        "INSERT INTO formula_items (category, title, content) VALUES (?, ?, ?)",
        (category.strip() or "高等数学", title.strip(), content.strip()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM formula_items WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return dict(row) if row is not None else None


def update_formula(
    conn: sqlite3.Connection,
    formula_id: int,
    category: str,
    title: str,
    content: str,
) -> Optional[dict]:
    """更新公式条目。"""
    row = conn.execute(
        "SELECT 1 FROM formula_items WHERE id = ?", (formula_id,)
    ).fetchone()
    if row is None:
        return None
    conn.execute(
        "UPDATE formula_items SET category = ?, title = ?, content = ?, "
        "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (category.strip() or "高等数学", title.strip(), content.strip(), formula_id),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM formula_items WHERE id = ?", (formula_id,)
    ).fetchone()
    return dict(updated) if updated is not None else None


def delete_formula(conn: sqlite3.Connection, formula_id: int) -> bool:
    """删除公式条目。"""
    row = conn.execute(
        "SELECT 1 FROM formula_items WHERE id = ?", (formula_id,)
    ).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM formula_items WHERE id = ?", (formula_id,))
    conn.commit()
    return True
