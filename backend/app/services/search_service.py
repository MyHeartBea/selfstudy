"""跨实体统一搜索：命令面板（Ctrl+K）一次问全站，而不是先选作用域再搜。

只读、五个实体各一条 `LIKE` 查询 + 一条同形状 `COUNT`。数据量级（百到千行）下
不需要 FTS；将来上 FTS5 也只换这个文件，响应形状已按"分组 + 每组 total"钉好。
"""

import sqlite3
from typing import Any, Dict, List

# (key, 显示名)。顺序即面板里的分组顺序：常搜的在前。
GROUPS = (
    ("mistakes", "错题"),
    ("knowledge", "知识点"),
    ("formulas", "公式"),
    ("vocab", "生词"),
    ("essays", "作文"),
)

_SNIPPET_RADIUS = 46


def like_pattern(q: str) -> str:
    """把用户输入包成 LIKE 模式，并转义 `%`/`_`/`\\`（配合 `ESCAPE '\\'` 使用）。

    不转义的话搜 `50%` 会命中一切含"5"再含任意后缀的内容 —— 通配符是用户内容的一部分，
    不是查询语法。全站任何"按关键词 LIKE"的地方都用它，别各自再抄一遍。
    """
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())


def _snippet(text: Any, q: str) -> str:
    """以命中位置为中心截一段，让"为什么匹配上"一眼可见。

    必须先把文本压成一行再来找下标：题干/正文里全是换行，直接 `find` 到的偏移量
    在原始文本里、切片却按折叠后的文本做，两边对不上，截取位置会漂。
    """
    flat = _clean(text)
    if not flat:
        return ""
    at = flat.lower().find(q.lower())
    if at < 0:
        # 匹配发生在被折叠掉的换行处（如 "自\n由"），折叠文本里搜不到就退回开头
        return flat[:_SNIPPET_RADIUS] + ("…" if len(flat) > _SNIPPET_RADIUS else "")
    start = max(0, at - _SNIPPET_RADIUS // 2)
    end = min(len(flat), at + len(q) + _SNIPPET_RADIUS)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")


def _fetch(
    conn: sqlite3.Connection,
    sql: str,
    count_sql: str,
    params: tuple,
    mapper,
    limit: int,
) -> Dict[str, Any]:
    total = conn.execute(count_sql, params).fetchone()[0]
    rows = conn.execute(sql, params + (limit,)).fetchall()
    return {"total": total, "items": [mapper(row) for row in rows]}


def search_all(conn: sqlite3.Connection, q: str, limit: int = 5) -> dict:
    """五个实体的全站搜索。返回 `{q, limit, total, groups:[{key,label,total,items}]}`。

    空组不返回（前端不必知道有几种实体）；`groups` 仍按 `GROUPS` 的顺序。
    """
    q = (q or "").strip()
    if not q:
        return {"q": "", "limit": limit, "total": 0, "groups": []}
    like = like_pattern(q)
    groups: List[dict] = []

    def add(key: str, label: str, result: dict) -> None:
        if result["items"]:
            groups.append({"key": key, "label": label, **result})

    add(
        "mistakes",
        "错题",
        _fetch(
            conn,
            "SELECT m.id, m.question, m.question_type, s.name AS subject "
            "FROM mistakes m LEFT JOIN subjects s ON s.id = m.subject_id "
            "WHERE m.question LIKE ? ESCAPE '\\' ORDER BY m.id DESC LIMIT ?",
            "SELECT COUNT(*) FROM mistakes WHERE question LIKE ? ESCAPE '\\'",
            (like,),
            lambda r: {
                "id": r["id"],
                "title": _snippet(r["question"], q),
                "subtitle": r["subject"] or "",
                "meta": r["question_type"] or "",
            },
            limit,
        ),
    )
    add(
        "knowledge",
        "知识点",
        _fetch(
            conn,
            "SELECT k.id, k.tag_name, k.summary, s.name AS subject "
            "FROM knowledge_base k LEFT JOIN subjects s ON s.id = k.subject_id "
            "WHERE k.tag_name LIKE ? ESCAPE '\\' OR k.summary LIKE ? ESCAPE '\\' "
            "ORDER BY k.id DESC LIMIT ?",
            "SELECT COUNT(*) FROM knowledge_base "
            "WHERE tag_name LIKE ? ESCAPE '\\' OR summary LIKE ? ESCAPE '\\'",
            (like, like),
            lambda r: {
                "id": r["id"],
                "title": r["tag_name"],
                "subtitle": _snippet(r["summary"], q),
                "meta": r["subject"] or "",
            },
            limit,
        ),
    )
    add(
        "formulas",
        "公式",
        _fetch(
            conn,
            "SELECT id, title, content, category FROM formula_items "
            "WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\' "
            "ORDER BY id DESC LIMIT ?",
            "SELECT COUNT(*) FROM formula_items "
            "WHERE title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'",
            (like, like),
            lambda r: {
                "id": r["id"],
                "title": r["title"],
                "subtitle": _snippet(r["content"], q),
                "meta": r["category"] or "",
            },
            limit,
        ),
    )
    add(
        "vocab",
        "生词",
        _fetch(
            conn,
            "SELECT id, word, meaning, kind FROM vocab_items "
            "WHERE word LIKE ? ESCAPE '\\' OR meaning LIKE ? ESCAPE '\\' "
            "ORDER BY id DESC LIMIT ?",
            "SELECT COUNT(*) FROM vocab_items "
            "WHERE word LIKE ? ESCAPE '\\' OR meaning LIKE ? ESCAPE '\\'",
            (like, like),
            lambda r: {
                "id": r["id"],
                "title": r["word"],
                "subtitle": _snippet(r["meaning"], q),
                "meta": r["kind"] or "",
            },
            limit,
        ),
    )
    add(
        "essays",
        "作文",
        _fetch(
            conn,
            "SELECT id, kind, prompt_text, essay_text, score, max_score FROM essay_records "
            "WHERE prompt_text LIKE ? ESCAPE '\\' OR essay_text LIKE ? ESCAPE '\\' "
            "ORDER BY id DESC LIMIT ?",
            "SELECT COUNT(*) FROM essay_records "
            "WHERE prompt_text LIKE ? ESCAPE '\\' OR essay_text LIKE ? ESCAPE '\\'",
            (like, like),
            lambda r: {
                "id": r["id"],
                "title": _snippet(r["prompt_text"] or r["essay_text"], q),
                "subtitle": _snippet(r["essay_text"], q) if r["prompt_text"] else "",
                "meta": f"{r['score']}/{r['max_score']}",
            },
            limit,
        ),
    )

    return {
        "q": q,
        "limit": limit,
        "total": sum(g["total"] for g in groups),
        "groups": groups,
    }
