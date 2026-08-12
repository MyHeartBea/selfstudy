"""知识点相关业务逻辑。"""

import sqlite3
from typing import Any, Dict, List, Optional, Union

# 知识点标签统一规范：变体一律归一到标准名，保证检索一致。
TAG_SYNONYMS = {
    "线性微分方程": "微分方程",
    "一阶微分方程": "微分方程",
    "一阶线性方程": "微分方程",
    "一阶线性微分方程": "微分方程",
    "常微分方程": "微分方程",
    "二阶常系数线性微分方程": "二阶线性方程",
    "二阶常系数线性方程": "二阶线性方程",
    "二阶线性微分方程": "二阶线性方程",
    "切线方程": "切线",
    "切线与导数": "切线",
    "分段求导": "分段函数",
    "分段函数与连续性": "分段函数",
    "求导法则": "导数",
    "导数运算": "导数",
    "幂函数求导": "导数",
    "极限与连续": "极限",
    "无穷小量": "极限",
}


def canonical_tags(tags: List[str]) -> List[str]:
    """把标签变体归一到标准名，并去重。"""
    result: List[str] = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        tag = TAG_SYNONYMS.get(tag, tag)
        if tag not in result:
            result.append(tag)
    return result


def ensure_knowledge_tags(
    conn: sqlite3.Connection,
    tags: List[str],
    subject_id: Optional[int],
    sub_subject_id: Optional[int],
) -> None:
    """错题保存时自动补全缺失的知识点词条。"""
    for tag in canonical_tags(tags):
        conn.execute(
            "INSERT OR IGNORE INTO knowledge_base "
            "(tag_name, subject_id, sub_subject_id, summary) VALUES (?, ?, ?, '')",
            (tag, subject_id, sub_subject_id),
        )


def knowledge_to_dict(row) -> dict:
    """把知识点行转为字典，并把关联标签字符串还原为数组。"""
    data = dict(row)
    related = data.get("related_tags") or ""
    data["related_tags"] = [
        tag.strip() for tag in related.split(",") if tag.strip()
    ]
    return data


def get_related_knowledge(
    conn: sqlite3.Connection,
    tag_names: List[str],
) -> List[dict]:
    """按关联标签名批量返回知识点词条，附带科目与二级科目名。"""
    names = canonical_tags(tag_names or [])
    if not names:
        return []
    placeholders = ", ".join("?" for _ in names)
    rows = conn.execute(
        "SELECT kb.*, s.name AS subject_name, ss.name AS sub_subject_name "
        "FROM knowledge_base kb "
        "LEFT JOIN subjects s ON s.id = kb.subject_id "
        "LEFT JOIN sub_subjects ss ON ss.id = kb.sub_subject_id "
        f"WHERE kb.tag_name IN ({placeholders}) "
        "ORDER BY kb.id",
        names,
    ).fetchall()
    return [knowledge_to_dict(row) for row in rows]


def list_knowledge(
    conn: sqlite3.Connection,
    subject_id: Optional[int] = None,
    sub_subject_id: Optional[int] = None,
    tag: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> Union[List[dict], Dict[str, Any]]:
    """按科目、二级科目、标签模糊搜索知识点；传 page 时返回分页结果。"""
    sql = (
        "SELECT kb.*, s.name AS subject_name, ss.name AS sub_subject_name "
        "FROM knowledge_base kb "
        "LEFT JOIN subjects s ON s.id = kb.subject_id "
        "LEFT JOIN sub_subjects ss ON ss.id = kb.sub_subject_id "
    )
    conditions = []
    params = []
    if subject_id is not None:
        conditions.append("kb.subject_id = ?")
        params.append(subject_id)
    if sub_subject_id is not None:
        conditions.append("kb.sub_subject_id = ?")
        params.append(sub_subject_id)
    if tag:
        conditions.append("kb.tag_name LIKE ?")
        params.append(f"%{tag}%")
    if conditions:
        where_sql = " WHERE " + " AND ".join(conditions)
    else:
        where_sql = ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM knowledge_base kb{where_sql}",
        params,
    ).fetchone()[0]
    sql += where_sql + " ORDER BY kb.created_at DESC, kb.id DESC"
    if page is not None:
        sql += " LIMIT ? OFFSET ?"
        rows = conn.execute(
            sql,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [knowledge_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    rows = conn.execute(sql, params).fetchall()
    return [knowledge_to_dict(row) for row in rows]


def get_by_tag(conn: sqlite3.Connection, tag: str) -> Optional[dict]:
    """按标签名精确获取知识点词条。"""
    row = conn.execute(
        "SELECT * FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE",
        (tag.strip(),),
    ).fetchone()
    return knowledge_to_dict(row) if row is not None else None


def update_knowledge(
    conn: sqlite3.Connection,
    knowledge_id: int,
    summary: str,
    subject_id: Optional[int] = None,
    sub_subject_id: Optional[int] = None,
    related_tags: Optional[List[str]] = None,
) -> Optional[dict]:
    """更新知识点摘要，并允许修正所属科目、二级科目与关联知识点。"""
    row = conn.execute("SELECT 1 FROM knowledge_base WHERE id = ?", (knowledge_id,)).fetchone()
    if row is None:
        return None
    if subject_id is not None:
        exists = conn.execute(
            "SELECT 1 FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        if exists is None:
            raise ValueError("所选科目不存在")
        if sub_subject_id is not None:
            sub_exists = conn.execute(
                "SELECT 1 FROM sub_subjects WHERE id = ? AND subject_id = ?",
                (sub_subject_id, subject_id),
            ).fetchone()
            if sub_exists is None:
                raise ValueError("二级科目不存在或与科目不匹配")
    elif sub_subject_id is not None:
        current = conn.execute(
            "SELECT subject_id FROM knowledge_base WHERE id = ?",
            (knowledge_id,),
        ).fetchone()
        sub_exists = conn.execute(
            "SELECT 1 FROM sub_subjects WHERE id = ? AND subject_id = ?",
            (sub_subject_id, current["subject_id"]),
        ).fetchone()
        if sub_exists is None:
            raise ValueError("二级科目不存在或与科目不匹配")

    sets = ["summary = ?"]
    params = [summary.strip()]
    related = canonical_tags(related_tags or [])
    sets.append("related_tags = ?")
    params.append(",".join(related))
    if subject_id is not None:
        sets.append("subject_id = ?")
        params.append(subject_id)
        sets.append("sub_subject_id = ?")
        params.append(sub_subject_id)
    elif sub_subject_id is not None:
        sets.append("sub_subject_id = ?")
        params.append(sub_subject_id)
    params.append(knowledge_id)
    conn.execute(
        f"UPDATE knowledge_base SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)).fetchone()
    return knowledge_to_dict(updated)


def delete_knowledge(conn: sqlite3.Connection, knowledge_id: int) -> bool:
    """删除知识点词条，不影响关联错题。"""
    row = conn.execute("SELECT 1 FROM knowledge_base WHERE id = ?", (knowledge_id,)).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM knowledge_base WHERE id = ?", (knowledge_id,))
    conn.commit()
    return True
