"""考研错题本后端服务（FastAPI + SQLite）。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "mistakes.db"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="考研错题本", description="单用户考研错题本 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- 数据库基础 ----------

def get_connection() -> sqlite3.Connection:
    """打开一个新的 SQLite 连接，每个请求独立使用。"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """初始化表结构，并在首次启动时写入演示数据。"""
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS sub_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id),
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id INTEGER NOT NULL REFERENCES subjects(id),
                sub_subject_id INTEGER REFERENCES sub_subjects(id),
                question TEXT NOT NULL,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_answer TEXT,
                analysis TEXT,
                difficulty INTEGER CHECK (difficulty BETWEEN 1 AND 5),
                knowledge_tags TEXT,
                approach TEXT,
                source TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT UNIQUE COLLATE NOCASE NOT NULL,
                subject_id INTEGER REFERENCES subjects(id),
                sub_subject_id INTEGER REFERENCES sub_subjects(id),
                summary TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur = conn.execute("SELECT COUNT(*) FROM subjects")
        if cur.fetchone()[0] == 0:
            seed_data(conn)
        conn.commit()
    finally:
        conn.close()


def seed_data(conn: sqlite3.Connection) -> None:
    """写入科目、二级科目、知识点和演示错题。"""
    subjects = [
        (1, "政治"),
        (2, "英语二"),
        (3, "数学二"),
        (4, "408计算机基础综合"),
    ]
    conn.executemany("INSERT INTO subjects (id, name) VALUES (?, ?)", subjects)

    sub_subjects = [
        (1, 4, "数据结构"),
        (2, 4, "计算机组成原理"),
        (3, 4, "计算机网络"),
        (4, 4, "操作系统"),
    ]
    conn.executemany(
        "INSERT INTO sub_subjects (id, subject_id, name) VALUES (?, ?, ?)",
        sub_subjects,
    )

    knowledge_rows = [
        (
            "二叉树遍历",
            4,
            1,
            "前序遍历：根左右；中序遍历：左根右；后序遍历：左右根。"
            "递归实现代码简洁，非递归遍历常用栈模拟，层次遍历使用队列。",
        ),
        (
            "虚拟内存",
            4,
            4,
            "虚拟内存将逻辑地址空间与物理内存分离，支持按需调页、页面置换"
            "（LRU、FIFO、Clock 等），并可通过页表完成地址转换。",
        ),
        (
            "定语从句",
            2,
            None,
            "定语从句由关系代词或关系副词引导，修饰名词或代词；"
            "关系词在从句中充当主语、宾语、状语等成分，需结合先行词判断。",
        ),
        (
            "马原辩证法",
            1,
            None,
            "唯物辩证法三大规律：对立统一规律、量变质变规律、否定之否定规律。"
            "注意区分辩证法与形而上学，以及联系、发展、矛盾等核心概念。",
        ),
    ]
    conn.executemany(
        "INSERT INTO knowledge_base (tag_name, subject_id, sub_subject_id, summary) "
        "VALUES (?, ?, ?, ?)",
        knowledge_rows,
    )

    mistakes = [
        (
            4,
            1,
            "已知一棵二叉树的中序遍历序列为 D B E A F C，后序遍历序列为 D E B F C A，"
            "则该二叉树的先序遍历序列是？",
            "A B D E C F",
            "A B C D E F",
            "A B E D C F",
            "A D B E F C",
            "A",
            "后序遍历最后一个结点是根结点 A；再用中序遍历将左右子树分开，"
            "递归还原可得先序遍历为 A B D E C F。",
            3,
            "二叉树遍历,递归",
            "递归还原",
            "2025 年真题改编",
        ),
        (
            2,
            None,
            "The reason ______ he was late for the meeting is still unknown.",
            "why",
            "which",
            "that",
            "where",
            "A",
            "先行词 reason 后常用关系副词 why 引导定语从句，说明原因；"
            "which/that 在从句中作主语或宾语，此处不符合。",
            2,
            "定语从句",
            "语法辨析",
            "英语二真题",
        ),
        (
            1,
            None,
            "下列选项中，体现量变质变规律的是？",
            "千里之行，始于足下",
            "城门失火，殃及池鱼",
            "一把钥匙开一把锁",
            "牵一发而动全身",
            "A",
            "“千里之行，始于足下”强调量的积累达到一定程度会引起质变；"
            "B 体现联系，C 体现矛盾特殊性，D 体现整体与部分。",
            1,
            "马原辩证法",
            "概念辨析",
            "政治模拟题",
        ),
    ]
    conn.executemany(
        "INSERT INTO mistakes (subject_id, sub_subject_id, question, option_a, "
        "option_b, option_c, option_d, correct_answer, analysis, difficulty, "
        "knowledge_tags, approach, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        mistakes,
    )


# ---------- 序列化与校验 ----------

def ok(data: Any, message: str = "success") -> dict:
    return {"code": 200, "data": data, "message": message}


def error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": status_code, "data": None, "message": message},
    )


def mistake_to_dict(row: sqlite3.Row) -> dict:
    """将错题行转为字典，并把标签字符串还原为数组。"""
    data = dict(row)
    tags = data.get("knowledge_tags") or ""
    data["knowledge_tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    return data


def normalize_tags(value: Any) -> List[str]:
    """把逗号字符串或数组统一整理为去重后的标签列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value]
    else:
        parts = [str(value)]
    result: List[str] = []
    for part in parts:
        part = part.strip()
        if part and part not in result:
            result.append(part)
    return result


def build_mistake_fields(body: Dict[str, Any], conn: sqlite3.Connection) -> Tuple[Optional[dict], List[str]]:
    """校验并整理错题字段，返回 (字段字典, 错误列表)。"""
    errors: List[str] = []

    subject_id = body.get("subject_id")
    if subject_id in (None, ""):
        errors.append("科目不能为空")
        subject_id = None
    else:
        try:
            subject_id = int(subject_id)
        except (TypeError, ValueError):
            errors.append("科目参数无效")
            subject_id = None
    if subject_id is not None:
        exists = conn.execute("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        if not exists:
            errors.append("所选科目不存在")

    sub_subject_id = body.get("sub_subject_id")
    if sub_subject_id in (None, ""):
        sub_subject_id = None
    else:
        try:
            sub_subject_id = int(sub_subject_id)
        except (TypeError, ValueError):
            errors.append("二级科目参数无效")
            sub_subject_id = None
    if sub_subject_id is not None and subject_id is not None:
        exists = conn.execute(
            "SELECT 1 FROM sub_subjects WHERE id = ? AND subject_id = ?",
            (sub_subject_id, subject_id),
        ).fetchone()
        if not exists:
            errors.append("二级科目不存在或与科目不匹配")
            sub_subject_id = None

    question = body.get("question")
    if question is None or not str(question).strip():
        errors.append("题干不能为空")
        question = ""
    else:
        question = str(question).strip()

    option_fields = {}
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = body.get(key)
        option_fields[key] = str(value).strip() if value is not None else ""

    correct_answer = body.get("correct_answer")
    if correct_answer in (None, ""):
        errors.append("正确答案不能为空")
        correct_answer = None
    else:
        correct_answer = str(correct_answer).strip().upper()
        if correct_answer not in ("A", "B", "C", "D"):
            errors.append("正确答案必须是 A/B/C/D 之一")
            correct_answer = None

    difficulty = body.get("difficulty")
    if difficulty in (None, ""):
        errors.append("难度不能为空")
        difficulty = None
    else:
        try:
            difficulty = int(difficulty)
        except (TypeError, ValueError):
            errors.append("难度必须是 1-5 的整数")
            difficulty = None
        else:
            if difficulty < 1 or difficulty > 5:
                errors.append("难度必须是 1-5 的整数")
                difficulty = None

    tags = normalize_tags(body.get("knowledge_tags"))
    analysis = str(body.get("analysis") or "").strip()
    approach = str(body.get("approach") or "").strip()
    source = str(body.get("source") or "").strip()

    if errors:
        return None, errors

    return {
        "subject_id": subject_id,
        "sub_subject_id": sub_subject_id,
        "question": question,
        "option_a": option_fields["option_a"],
        "option_b": option_fields["option_b"],
        "option_c": option_fields["option_c"],
        "option_d": option_fields["option_d"],
        "correct_answer": correct_answer,
        "analysis": analysis,
        "difficulty": difficulty,
        "knowledge_tags": tags,
        "knowledge_tags_text": ",".join(tags),
        "approach": approach,
        "source": source,
    }, []


MISTAKE_COLUMNS = (
    "subject_id",
    "sub_subject_id",
    "question",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "analysis",
    "difficulty",
    "knowledge_tags",
    "approach",
    "source",
)

MISTAKE_FIELD_KEYS = {
    "knowledge_tags": "knowledge_tags_text",
}


def mistake_field(fields: dict, column: str) -> Any:
    """根据数据库列名取对应的字段值。"""
    return fields[MISTAKE_FIELD_KEYS.get(column, column)]


def ensure_knowledge_tags(
    conn: sqlite3.Connection,
    tags: List[str],
    subject_id: Optional[int],
    sub_subject_id: Optional[int],
) -> None:
    """错题保存时自动补全缺失的知识点词条。"""
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO knowledge_base "
            "(tag_name, subject_id, sub_subject_id, summary) VALUES (?, ?, ?, '')",
            (tag, subject_id, sub_subject_id),
        )


# ---------- 错题 API ----------

@app.get("/api/mistakes")
def list_mistakes(
    subject_id: Optional[int] = Query(None),
    sub_subject_id: Optional[int] = Query(None),
    difficulty: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
    approach: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("created_desc"),
):
    """按条件筛选错题，默认按创建时间倒序。"""
    if difficulty is not None and (difficulty < 1 or difficulty > 5):
        return error(400, "难度必须是 1-5")
    try:
        conn = get_connection()
        try:
            conditions: List[str] = []
            params: List[Any] = []
            if subject_id is not None:
                conditions.append("subject_id = ?")
                params.append(subject_id)
            if sub_subject_id is not None:
                conditions.append("sub_subject_id = ?")
                params.append(sub_subject_id)
            if difficulty is not None:
                conditions.append("difficulty = ?")
                params.append(difficulty)
            if tag:
                conditions.append("knowledge_tags LIKE ?")
                params.append(f"%{tag}%")
            if approach:
                conditions.append("approach LIKE ?")
                params.append(f"%{approach}%")
            if search:
                conditions.append("question LIKE ?")
                params.append(f"%{search}%")

            sort_map = {
                "created_desc": "created_at DESC, id DESC",
                "difficulty_desc": "difficulty DESC, created_at DESC",
                "difficulty_asc": "difficulty ASC, created_at DESC",
            }
            order_by = sort_map.get(sort, sort_map["created_desc"])

            sql = "SELECT * FROM mistakes"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY " + order_by

            rows = conn.execute(sql, params).fetchall()
            return ok([mistake_to_dict(row) for row in rows])
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询错题失败：{exc}")


@app.get("/api/mistakes/{mistake_id}")
def get_mistake(mistake_id: int):
    """返回错题详情，附带知识点补充与同知识点错题。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
            if row is None:
                return error(404, "错题不存在")

            data = mistake_to_dict(row)
            first_tag = data["knowledge_tags"][0] if data["knowledge_tags"] else None
            knowledge_extra = None
            related_mistakes: List[dict] = []

            if first_tag:
                krow = conn.execute(
                    "SELECT * FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE",
                    (first_tag,),
                ).fetchone()
                if krow is not None:
                    knowledge_extra = dict(krow)
                related_rows = conn.execute(
                    "SELECT * FROM mistakes "
                    "WHERE instr(',' || knowledge_tags || ',', ?) > 0 AND id != ? "
                    "ORDER BY created_at DESC, id DESC LIMIT 5",
                    (f",{first_tag},", mistake_id),
                ).fetchall()
                related_mistakes = [mistake_to_dict(row) for row in related_rows]

            data["knowledge_extra"] = knowledge_extra
            data["related_mistakes"] = related_mistakes
            return ok(data)
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询错题详情失败：{exc}")


@app.post("/api/mistakes")
def create_mistake(body: dict = Body(...)):
    """新建错题，并自动创建缺失的知识点词条。"""
    try:
        conn = get_connection()
        try:
            fields, errors = build_mistake_fields(body, conn)
            if errors:
                return error(400, "；".join(errors))

            ensure_knowledge_tags(
                conn,
                fields["knowledge_tags"],
                fields["subject_id"],
                fields["sub_subject_id"],
            )
            cur = conn.execute(
                f"INSERT INTO mistakes ({', '.join(MISTAKE_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in MISTAKE_COLUMNS)})",
                tuple(mistake_field(fields, column) for column in MISTAKE_COLUMNS),
            )
            conn.commit()

            created = conn.execute("SELECT * FROM mistakes WHERE id = ?", (cur.lastrowid,)).fetchone()
            return ok(mistake_to_dict(created), "错题创建成功")
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"创建错题失败：{exc}")


@app.put("/api/mistakes/{mistake_id}")
def update_mistake(mistake_id: int, body: dict = Body(...)):
    """更新指定错题，同时补全缺失的知识点词条。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
            if row is None:
                return error(404, "错题不存在")

            fields, errors = build_mistake_fields(body, conn)
            if errors:
                return error(400, "；".join(errors))

            ensure_knowledge_tags(
                conn,
                fields["knowledge_tags"],
                fields["subject_id"],
                fields["sub_subject_id"],
            )
            assignments = ", ".join(f"{column} = ?" for column in MISTAKE_COLUMNS)
            conn.execute(
                f"UPDATE mistakes SET {assignments} WHERE id = ?",
                tuple(mistake_field(fields, column) for column in MISTAKE_COLUMNS) + (mistake_id,),
            )
            conn.commit()

            updated = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
            return ok(mistake_to_dict(updated), "错题更新成功")
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"更新错题失败：{exc}")


@app.delete("/api/mistakes/{mistake_id}")
def delete_mistake(mistake_id: int):
    """删除指定错题。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
            if row is None:
                return error(404, "错题不存在")
            conn.execute("DELETE FROM mistakes WHERE id = ?", (mistake_id,))
            conn.commit()
            return ok({"id": mistake_id}, "错题删除成功")
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"删除错题失败：{exc}")


# ---------- 知识点 API ----------

@app.get("/api/knowledge")
def list_knowledge(
    subject_id: Optional[int] = Query(None),
    sub_subject_id: Optional[int] = Query(None),
    tag: Optional[str] = Query(None),
):
    """按科目、二级科目、标签模糊搜索知识点。"""
    try:
        conn = get_connection()
        try:
            sql = (
                "SELECT kb.*, s.name AS subject_name, ss.name AS sub_subject_name "
                "FROM knowledge_base kb "
                "LEFT JOIN subjects s ON s.id = kb.subject_id "
                "LEFT JOIN sub_subjects ss ON ss.id = kb.sub_subject_id "
                "WHERE 1 = 1"
            )
            conditions: List[str] = []
            params: List[Any] = []
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
                sql += " AND " + " AND ".join(conditions)
            sql += " ORDER BY kb.created_at DESC, kb.id DESC"

            rows = conn.execute(sql, params).fetchall()
            return ok([dict(row) for row in rows])
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询知识点失败：{exc}")


@app.get("/api/knowledge/by-tag")
def get_knowledge_by_tag(tag: str = Query(..., min_length=1)):
    """按标签名精确获取知识点词条。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE",
                (tag.strip(),),
            ).fetchone()
            if row is None:
                return error(404, "知识点不存在")
            return ok(dict(row))
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询知识点失败：{exc}")


@app.put("/api/knowledge/{knowledge_id}")
def update_knowledge(knowledge_id: int, body: dict = Body(...)):
    """更新知识点摘要。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM knowledge_base WHERE id = ?", (knowledge_id,)).fetchone()
            if row is None:
                return error(404, "知识点不存在")
            summary = str(body.get("summary") or "").strip()
            conn.execute(
                "UPDATE knowledge_base SET summary = ? WHERE id = ?",
                (summary, knowledge_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM knowledge_base WHERE id = ?", (knowledge_id,)
            ).fetchone()
            return ok(dict(updated), "知识点更新成功")
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"更新知识点失败：{exc}")


@app.delete("/api/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: int):
    """删除知识点词条，不影响关联错题。"""
    try:
        conn = get_connection()
        try:
            row = conn.execute("SELECT 1 FROM knowledge_base WHERE id = ?", (knowledge_id,)).fetchone()
            if row is None:
                return error(404, "知识点不存在")
            conn.execute("DELETE FROM knowledge_base WHERE id = ?", (knowledge_id,))
            conn.commit()
            return ok({"id": knowledge_id}, "知识点删除成功")
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"删除知识点失败：{exc}")


# ---------- 统计与基础数据 API ----------

@app.get("/api/stats")
def get_stats():
    """返回总错题数、今日新增和按科目统计。"""
    try:
        conn = get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0]
            today_new = conn.execute(
                "SELECT COUNT(*) FROM mistakes "
                "WHERE date(created_at, 'localtime') = date('now', 'localtime')"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT s.id AS subject_id, s.name AS name, "
                "COUNT(m.id) AS count, "
                "ROUND(COALESCE(AVG(m.difficulty), 0), 2) AS avg_difficulty "
                "FROM subjects s "
                "LEFT JOIN mistakes m ON m.subject_id = s.id "
                "GROUP BY s.id, s.name ORDER BY s.id"
            ).fetchall()
            return ok(
                {
                    "total_mistakes": total,
                    "today_new": today_new,
                    "by_subject": [dict(row) for row in rows],
                }
            )
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"获取统计失败：{exc}")


@app.get("/api/subjects")
def list_subjects():
    """返回全部科目。"""
    try:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM subjects ORDER BY id").fetchall()
            return ok([dict(row) for row in rows])
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询科目失败：{exc}")


@app.get("/api/sub_subjects")
def list_sub_subjects(subject_id: Optional[int] = Query(None)):
    """返回二级科目，可按科目筛选。"""
    try:
        conn = get_connection()
        try:
            if subject_id is None:
                rows = conn.execute("SELECT * FROM sub_subjects ORDER BY id").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sub_subjects WHERE subject_id = ? ORDER BY id",
                    (subject_id,),
                ).fetchall()
            return ok([dict(row) for row in rows])
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"查询二级科目失败：{exc}")


# ---------- 导出与导入 ----------

@app.get("/api/export")
def export_data():
    """导出全部错题与知识点，便于备份和迁移。"""
    try:
        conn = get_connection()
        try:
            mistakes = [
                mistake_to_dict(row)
                for row in conn.execute("SELECT * FROM mistakes ORDER BY id").fetchall()
            ]
            knowledge = [
                dict(row)
                for row in conn.execute("SELECT * FROM knowledge_base ORDER BY id").fetchall()
            ]
            return ok(
                {
                    "mistakes": mistakes,
                    "knowledge": knowledge,
                    "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"导出失败：{exc}")


@app.post("/api/import")
def import_mistakes(body: dict = Body(...)):
    """批量导入错题，自动处理知识点词条。"""
    raw = body.get("mistakes") if isinstance(body, dict) else body
    if not isinstance(raw, list):
        return error(400, "导入数据格式错误，应为 mistakes 数组")
    try:
        conn = get_connection()
        try:
            created = 0
            failed: List[dict] = []
            for index, item in enumerate(raw):
                if not isinstance(item, dict):
                    failed.append({"index": index, "error": "条目不是 JSON 对象"})
                    continue
                fields, errors = build_mistake_fields(item, conn)
                if errors:
                    failed.append({"index": index, "error": "；".join(errors)})
                    continue
                ensure_knowledge_tags(
                    conn,
                    fields["knowledge_tags"],
                    fields["subject_id"],
                    fields["sub_subject_id"],
                )
                conn.execute(
                    f"INSERT INTO mistakes ({', '.join(MISTAKE_COLUMNS)}) "
                    f"VALUES ({', '.join('?' for _ in MISTAKE_COLUMNS)})",
                    tuple(mistake_field(fields, column) for column in MISTAKE_COLUMNS),
                )
                created += 1
            conn.commit()
            return ok(
                {"created": created, "failed": failed},
                f"成功导入 {created} 条错题",
            )
        finally:
            conn.close()
    except Exception as exc:
        return error(500, f"导入失败：{exc}")


# ---------- 初始化与静态文件 ----------

init_db()

if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
