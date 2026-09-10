"""知识点相关业务逻辑。"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

# 注意：不能在模块顶层 `from app.database import mistake_to_dict`——
# database.py 反过来要 import 本模块的 canonical_tags，会形成循环导入。
# 这里在使用处局部导入。

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


def _mistake_to_dict(row) -> dict:
    """局部包装：避免与 app.database 的循环导入（见文件顶部说明）。"""
    from app.database import mistake_to_dict

    return mistake_to_dict(row)


def get_knowledge_mistakes(
    conn: sqlite3.Connection,
    tag_name: str,
    limit: int = 50,
    related_tags: Optional[List[str]] = None,
) -> dict:
    """知识点 ↔ 错题双向链接：返回该知识点关联的错题与其掌握情况。

    关联依据 `mistake_tag_map`（错题的知识点标签）。**知识点名与错题标签常常不完全同名**
    （实测 134 个知识点里只有 83 个能直接按同名对上），所以这里允许传入该知识点的
    `related_tags` 作为兜底：名称没命中时，再用关联标签去找错题，并标明命中方式。

    返回里同时给出汇总统计（几题、平均掌握度、总错误次数、到期数、未复习数），
    供知识点详情弹窗展示"这个知识点掌握得怎么样 / 一键练这些题"。
    """
    tag = str(tag_name or "").strip()
    if not tag:
        return {
            "tag_name": tag,
            "matched_by": "none",
            "matched_tags": [],
            "hit_tags": [],
            "total": 0,
            "items": [],
            "stats": {},
        }

    direct = conn.execute(
        "SELECT COUNT(*) AS c FROM mistake_tag_map WHERE tag = ?", (tag,)
    ).fetchone()["c"]

    direct_match = bool(direct)

    tags = [tag]
    if not direct:
        # 名称没直接命中 → 用关联标签兜底（去重、去掉空值）
        extras = []
        for item in related_tags or []:
            item = str(item or "").strip()
            if item and item not in tags:
                extras.append(item)
        tags = extras if extras else [tag]

    placeholders = ", ".join("?" for _ in tags)
    rows = conn.execute(
        "SELECT DISTINCT m.* FROM mistakes m "
        "JOIN mistake_tag_map t ON t.mistake_id = m.id "
        f"WHERE t.tag IN ({placeholders}) "
        "ORDER BY m.wrong_count DESC, m.mastery_level ASC, m.id DESC "
        "LIMIT ?",
        (*tags, limit),
    ).fetchall()
    items = [_mistake_to_dict(row) for row in rows]

    stats_row = conn.execute(
        "SELECT COUNT(DISTINCT m.id) AS total, "
        "COALESCE(AVG(m.mastery_level), 0) AS avg_mastery, "
        "COALESCE(SUM(m.wrong_count), 0) AS wrong_total, "
        "COALESCE(SUM(m.review_count), 0) AS review_total, "
        "COALESCE(SUM(CASE WHEN m.next_review_at IS NULL "
        "  OR m.next_review_at <= datetime('now') THEN 1 ELSE 0 END), 0) AS due_now, "
        "COALESCE(SUM(CASE WHEN m.review_count = 0 THEN 1 ELSE 0 END), 0) AS never_reviewed "
        f"FROM mistakes m JOIN mistake_tag_map t ON t.mistake_id = m.id "
        f"WHERE t.tag IN ({placeholders})",
        tuple(tags),
    ).fetchone()

    # matched_by：名称直接命中 / 靠 related_tags 兜底命中 / 两种情况都没找到错题
    if direct_match:
        matched_by = "tag_name"
    elif int(stats_row["total"] or 0) > 0:
        matched_by = "related_tags"
    else:
        matched_by = "none"

    # hit_tags：本次查询用到的标签里，**真正挂有错题**的那些（前端展示"通过哪些标签关联到"）
    hit_rows = conn.execute(
        f"SELECT DISTINCT tag FROM mistake_tag_map WHERE tag IN ({placeholders}) ORDER BY tag",
        tuple(tags),
    ).fetchall()
    hit_tags = [r["tag"] for r in hit_rows]

    return {
        "tag_name": tag,
        "matched_by": matched_by,
        "matched_tags": tags,
        "hit_tags": hit_tags,
        "total": int(stats_row["total"] or 0),
        "items": items,
        "stats": {
            "avg_mastery": round(float(stats_row["avg_mastery"] or 0), 2),
            "wrong_total": int(stats_row["wrong_total"] or 0),
            "review_total": int(stats_row["review_total"] or 0),
            "due_now": int(stats_row["due_now"] or 0),
            "never_reviewed": int(stats_row["never_reviewed"] or 0),
            "shown": len(items),
        },
    }


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
        # 只传 page 不传 page_size 时兜底默认值，避免 (page-1)*None 抛 TypeError
        page_size = page_size or 20
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
    summary: Optional[str] = None,
    subject_id: Optional[int] = None,
    sub_subject_id: Optional[int] = None,
    related_tags: Optional[List[str]] = None,
) -> Optional[dict]:
    """更新知识点摘要，并允许修正所属科目、二级科目与关联知识点。

    PATCH 语义：为 None 的字段保持不变，杜绝空 body 误清空数据。
    """
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

    sets = []
    params = []
    if summary is not None:
        sets.append("summary = ?")
        params.append(summary.strip())
    if related_tags is not None:
        related = canonical_tags(related_tags)
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
    if not sets:
        # 没有字段需要更新：直接返回当前行
        updated = conn.execute(
            "SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)
        ).fetchone()
        return knowledge_to_dict(updated)
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


def create_knowledge(
    conn: sqlite3.Connection,
    body: Dict[str, Any],
) -> Tuple[Optional[dict], List[str]]:
    """手动创建知识点词条（标签名唯一，重名报错）。"""
    errors: List[str] = []
    raw_tag = str(body.get("tag_name") or "").strip()
    if not raw_tag:
        errors.append("知识点名称不能为空")
        return None, errors
    tag_name = canonical_tags([raw_tag])[0]

    subject_id = body.get("subject_id")
    if subject_id in (None, ""):
        subject_id = None
    else:
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            errors.append("科目参数无效")
            subject_id = None
        else:
            exists = conn.execute(
                "SELECT 1 FROM subjects WHERE id = ?", (subject_id,)
            ).fetchone()
            if exists is None:
                errors.append("所选科目不存在")

    sub_subject_id = body.get("sub_subject_id")
    if sub_subject_id in (None, ""):
        sub_subject_id = None
    elif subject_id is not None:
        try:
            sub_subject_id = int(sub_subject_id)
        except (TypeError, ValueError):
            errors.append("二级科目参数无效")
            sub_subject_id = None
        else:
            sub_exists = conn.execute(
                "SELECT 1 FROM sub_subjects WHERE id = ? AND subject_id = ?",
                (sub_subject_id, subject_id),
            ).fetchone()
            if sub_exists is None:
                errors.append("二级科目不存在或与科目不匹配")
                sub_subject_id = None

    summary = str(body.get("summary") or "").strip()
    related = canonical_tags(body.get("related_tags") or [])

    if errors:
        return None, errors

    exists = conn.execute(
        "SELECT id FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE",
        (tag_name,),
    ).fetchone()
    if exists is not None:
        return None, [f"知识点「{tag_name}」已存在，请直接编辑其摘要"]

    cur = conn.execute(
        "INSERT INTO knowledge_base (tag_name, subject_id, sub_subject_id, summary, related_tags) "
        "VALUES (?, ?, ?, ?, ?)",
        (tag_name, subject_id, sub_subject_id, summary, ",".join(related)),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM knowledge_base WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return knowledge_to_dict(row), []
