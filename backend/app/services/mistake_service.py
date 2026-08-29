"""错题相关业务逻辑。"""

import base64
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config import PROJECT_ROOT, settings
from app.database import (
    mistake_field,
    mistake_tag_condition,
    mistake_to_dict,
    normalize_tags,
    sync_mistake_tags,
)
from app.models.tables import MISTAKE_COLUMNS
from app.services.knowledge_service import (
    canonical_tags,
    ensure_knowledge_tags,
    get_related_knowledge,
    knowledge_to_dict,
)

SOURCE_TYPES = {"real_exam", "mock", "other"}

IMAGE_DIR: Path = PROJECT_ROOT / "data" / "images"
IMAGE_MAX_BYTES = 8 * 1024 * 1024  # 单张图片 base64 解码后上限 8MB
IMAGE_MAX_COUNT = 5


def _images_dir() -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_DIR


def _save_image_data(data: bytes, mime: str = "") -> str:
    """把图片字节存到 data/images/，返回相对路径 images/<name>。<name> 为 uuid + 扩展名。"""
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    ext = ext_map.get(mime.strip().lower(), ".png")
    name = f"{uuid.uuid4().hex}{ext}"
    (_images_dir() / name).write_bytes(data)
    return f"images/{name}"


def process_images(images: Optional[List[Any]]) -> List[str]:
    """把请求里的 images 列表归一为相对路径列表。

    元素可为：
    - data URL（data:image/...;base64,...）→ 解码存文件，返回新路径
    - 裸 base64 → 按 PNG 解码存文件
    - 已有相对路径（images/xxx.png）→ 原样保留（编辑时不重复上传）
    单张超过 IMAGE_MAX_BYTES 时抛出 ValueError。
    """
    if not images:
        return []
    if not isinstance(images, list):
        raise ValueError("images 必须是数组")
    if len(images) > IMAGE_MAX_COUNT:
        raise ValueError(f"最多上传 {IMAGE_MAX_COUNT} 张图片")

    result: List[str] = []
    data_url_re = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+)?(;base64)?,(.*)$", re.S)
    for item in images:
        if item is None:
            continue
        text = str(item).strip()
        if not text:
            continue
        # 已有相对路径（编辑保留）
        if text.startswith("images/") and not text.startswith("images/.."):
            result.append(text)
            continue
        # data URL 或裸 base64
        mime = ""
        match = data_url_re.match(text)
        if match:
            mime = match.group(1) or ""
            payload = match.group(3)
        else:
            payload = text
        try:
            data = base64.b64decode(payload)
        except (ValueError, TypeError):
            raise ValueError("图片数据不是有效的 base64")
        if not data:
            continue
        if len(data) > IMAGE_MAX_BYTES:
            raise ValueError("单张图片不能超过 8MB")
        result.append(_save_image_data(data, mime))
    return result


def remove_image_files(paths: Optional[List[str]]) -> None:
    """删除不再引用的图片文件（吞掉 IO 错误，避免影响主流程）。"""
    for path in paths or []:
        try:
            rel = str(path)
            if rel.startswith("images/") and ".." not in rel.replace("\\", "/").split("/"):
                (_images_dir() / Path(rel).name).unlink(missing_ok=True)
        except OSError:
            pass


def validate_source_type(source_type: str) -> str:
    """归一并校验来源分类，返回归一后的值；非法时抛 ValueError。"""
    source_type = str(source_type or "other").strip().lower()
    if source_type == "self":
        source_type = "other"
    if source_type not in SOURCE_TYPES:
        raise ValueError("来源分类只能是真题/模拟题/自编/其他")
    return source_type


def validate_source_requirements(
    source_type: str,
    source_year: str,
    source_name: str,
) -> Optional[str]:
    """校验来源必填项，返回错误信息；合法时返回 None。"""
    source_type = str(source_type or "other").strip().lower()
    if source_type == "self":
        source_type = "other"
    if source_type == "real_exam" and not str(source_year or "").strip():
        return "真题必须填写年份"
    if source_type == "mock" and (
        not str(source_year or "").strip() or not str(source_name or "").strip()
    ):
        return "模拟题必须填写年份和试卷名称"
    return None


def build_mistake_fields(
    body: Dict[str, Any],
    conn: sqlite3.Connection,
    *,
    skip_subject_check: bool = False,
) -> Tuple[Optional[dict], List[str]]:
    """校验并整理错题字段，返回 (字段字典, 错误列表)。

    skip_subject_check=True 时跳过科目存在性查询（调用方已预校验，
    用于批量导入避免逐条 N+1）。
    """
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
    if subject_id is not None and not skip_subject_check:
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
    if (
        sub_subject_id is not None
        and subject_id is not None
        and not skip_subject_check
    ):
        exists = conn.execute(
            "SELECT 1 FROM sub_subjects WHERE id = ? AND subject_id = ?",
            (sub_subject_id, subject_id),
        ).fetchone()
        if not exists:
            errors.append("二级科目不存在或与科目不匹配")
            sub_subject_id = None

    question_type = str(body.get("question_type") or "choice").strip().lower()
    if question_type not in ("choice", "multi", "fill", "translation", "solution"):
        errors.append("题型不在支持范围内")
        question_type = "choice"

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

    correct_answer = str(body.get("correct_answer") or "").strip()
    if question_type == "choice":
        if not correct_answer:
            errors.append("选择题必须填写正确答案")
            correct_answer = None
        else:
            upper = correct_answer.upper()
            if upper not in ("A", "B", "C", "D"):
                errors.append("选择题正确答案必须是 A/B/C/D 之一")
                correct_answer = None
            else:
                correct_answer = upper
    elif question_type == "multi":
        # 政治多选：正确答案是 1-4 个字母（去重排序后存库），口径与判分一致
        from app.services.answer_service import normalize_multi_answer

        normalized = normalize_multi_answer(correct_answer)
        if not normalized:
            errors.append("多选题必须填写正确答案（如 ABD）")
            correct_answer = None
        else:
            correct_answer = normalized

    aliases = normalize_tags(body.get("answer_aliases"))

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

    difficulty_points = str(body.get("difficulty_points") or "").strip()
    if not difficulty_points:
        errors.append("主要难点简析不能为空")
    tags = canonical_tags(normalize_tags(body.get("knowledge_tags")))
    analysis = str(body.get("analysis") or "").strip()
    if not analysis:
        errors.append("解析不能为空")
    approach = str(body.get("approach") or "").strip()
    source = str(body.get("source") or "").strip()
    source_type = validate_source_type(body.get("source_type") or "other")
    source_year = str(body.get("source_year") or "").strip()
    source_name = str(body.get("source_name") or "").strip()
    source_issue = validate_source_requirements(source_type, source_year, source_name)
    if source_issue:
        errors.append(source_issue)

    if errors:
        return None, errors

    try:
        images = process_images(body.get("images"))
    except ValueError as exc:
        errors.append(str(exc))
        images = []
    if errors:
        return None, errors

    return {
        "subject_id": subject_id,
        "sub_subject_id": sub_subject_id,
        "question_type": question_type,
        "question": question,
        "option_a": option_fields["option_a"],
        "option_b": option_fields["option_b"],
        "option_c": option_fields["option_c"],
        "option_d": option_fields["option_d"],
        "correct_answer": correct_answer,
        "answer_aliases": aliases,
        "answer_aliases_text": ";;".join(aliases),
        "analysis": analysis,
        "difficulty": difficulty,
        "difficulty_points": difficulty_points,
        "knowledge_tags": tags,
        "knowledge_tags_text": ",".join(tags),
        "approach": approach,
        "source": source,
        "source_type": source_type,
        "source_year": source_year,
        "source_name": source_name,
        "images": images,
        "images_text": json.dumps(images, ensure_ascii=False),
    }, []


def list_approaches(conn: sqlite3.Connection, limit: int = 200) -> List[str]:
    """返回已有错题中出现过的解题思路，用于表单联想。"""
    rows = conn.execute(
        "SELECT DISTINCT approach FROM mistakes "
        "WHERE approach IS NOT NULL AND TRIM(approach) != '' "
        "ORDER BY approach LIMIT ?",
        (limit,),
    ).fetchall()
    return [row["approach"] for row in rows]


def list_mistakes(
    conn: sqlite3.Connection,
    filters: Dict[str, Any],
    page: Optional[int] = None,
    page_size: Optional[int] = None,
) -> Union[List[dict], Dict[str, Any]]:
    """按条件筛选错题；传 page 时返回分页结果。"""
    conditions: List[str] = []
    params: List[Any] = []

    if filters.get("subject_id") is not None:
        conditions.append("subject_id = ?")
        params.append(filters["subject_id"])
    if filters.get("sub_subject_id") is not None:
        conditions.append("sub_subject_id = ?")
        params.append(filters["sub_subject_id"])
    difficulty = filters.get("difficulty")
    if isinstance(difficulty, list) and difficulty:
        placeholders = ", ".join("?" for _ in difficulty)
        conditions.append(f"difficulty IN ({placeholders})")
        params.extend(int(item) for item in difficulty)
    elif difficulty is not None:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if filters.get("tag"):
        tag = str(filters["tag"]).strip()
        if tag:
            conditions.append(mistake_tag_condition(alias="mistakes"))
            params.append(tag)
    if filters.get("approach"):
        conditions.append("approach LIKE ?")
        params.append(f"%{filters['approach']}%")
    if filters.get("search"):
        conditions.append("question LIKE ?")
        params.append(f"%{filters['search']}%")
    if filters.get("source_type"):
        conditions.append("source_type = ?")
        params.append(filters["source_type"])
    if filters.get("source_year"):
        conditions.append("source_year = ?")
        params.append(filters["source_year"])
    if filters.get("question_type"):
        conditions.append("question_type = ?")
        params.append(filters["question_type"])

    sort_map = {
        "created_desc": "created_at DESC, id DESC",
        "difficulty_desc": "difficulty DESC, created_at DESC",
        "difficulty_asc": "difficulty ASC, created_at DESC",
    }
    order_by = sort_map.get(filters.get("sort", "created_desc"), sort_map["created_desc"])

    where_sql = ""
    if conditions:
        where_sql = " WHERE " + " AND ".join(conditions)
    total = conn.execute(
        f"SELECT COUNT(*) FROM mistakes{where_sql}",
        params,
    ).fetchone()[0]

    sql = "SELECT * FROM mistakes" + where_sql
    sql += " ORDER BY " + order_by
    if page is not None:
        # 只传 page 不传 page_size 时兜底默认值，避免 (page-1)*None 抛 TypeError
        page_size = page_size or 20
        sql += " LIMIT ? OFFSET ?"
        rows = conn.execute(
            sql,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        return {
            "items": [mistake_to_dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    rows = conn.execute(sql, params).fetchall()
    return [mistake_to_dict(row) for row in rows]


def get_mistake_detail(conn: sqlite3.Connection, mistake_id: int) -> Optional[dict]:
    """返回错题详情，附带知识点补充与同知识点错题。"""
    row = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    if row is None:
        return None

    data = mistake_to_dict(row)
    first_tag = data["knowledge_tags"][0] if data["knowledge_tags"] else None
    knowledge_extra = None
    related_mistakes: List[dict] = []
    related_knowledge: List[dict] = []

    if first_tag:
        krow = conn.execute(
            "SELECT * FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE",
            (first_tag,),
        ).fetchone()
        if krow is not None:
            knowledge_extra = knowledge_to_dict(krow)
            related_knowledge = get_related_knowledge(
                conn,
                knowledge_extra["related_tags"],
            )
        related_rows = conn.execute(
            "SELECT * FROM mistakes "
            f"WHERE {mistake_tag_condition(alias='mistakes')} AND id != ? "
            "ORDER BY created_at DESC, id DESC LIMIT 5",
            (first_tag, mistake_id),
        ).fetchall()
        related_mistakes = [mistake_to_dict(row) for row in related_rows]

    data["knowledge_extra"] = knowledge_extra
    data["related_knowledge"] = related_knowledge
    data["related_mistakes"] = related_mistakes

    grade_row = conn.execute(
        "SELECT id, score, verdict, created_at, errors, strengths, "
        "solution, alternate_methods FROM solution_grades "
        "WHERE mistake_id = ? ORDER BY id DESC LIMIT 1",
        (mistake_id,),
    ).fetchone()
    if grade_row is not None:
        grade = dict(grade_row)
        for column in ("errors", "strengths", "alternate_methods"):
            raw = grade.get(column) or ""
            try:
                grade[column] = json.loads(raw) if raw else []
            except (TypeError, ValueError):
                grade[column] = []
        data["last_grade"] = grade
    else:
        data["last_grade"] = None
    return data


def create_mistake(conn: sqlite3.Connection, body: Dict[str, Any]) -> Tuple[Optional[dict], List[str]]:
    """新建错题，并自动创建缺失的知识点词条。"""
    fields, errors = build_mistake_fields(body, conn)
    if errors:
        return None, errors

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
    sync_mistake_tags(conn, cur.lastrowid, fields["knowledge_tags"])
    conn.commit()
    created = conn.execute("SELECT * FROM mistakes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return mistake_to_dict(created), []


def update_mistake(
    conn: sqlite3.Connection,
    mistake_id: int,
    body: Dict[str, Any],
) -> Tuple[Optional[dict], List[str]]:
    """更新指定错题，同时补全缺失的知识点词条。"""
    row = conn.execute("SELECT images FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    if row is None:
        return None, ["NOT_FOUND"]
    old_images = []
    if row["images"]:
        try:
            old_images = json.loads(row["images"])
        except (TypeError, ValueError):
            old_images = []

    fields, errors = build_mistake_fields(body, conn)
    if errors:
        return None, errors

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
    sync_mistake_tags(conn, mistake_id, fields["knowledge_tags"])
    conn.commit()
    # 清理被替换掉的旧图片文件（新集合不再引用的）
    new_images = fields.get("images") or []
    removed = [path for path in old_images if path not in new_images]
    if removed:
        remove_image_files(removed)
    updated = conn.execute("SELECT * FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    return mistake_to_dict(updated), []


def delete_mistake(conn: sqlite3.Connection, mistake_id: int) -> bool:
    """删除指定错题，返回是否删除成功。"""
    row = conn.execute("SELECT images FROM mistakes WHERE id = ?", (mistake_id,)).fetchone()
    if row is None:
        return False
    old_images = []
    if row["images"]:
        try:
            old_images = json.loads(row["images"])
        except (TypeError, ValueError):
            old_images = []
    conn.execute("DELETE FROM solution_grades WHERE mistake_id = ?", (mistake_id,))
    conn.execute("DELETE FROM review_records WHERE mistake_id = ?", (mistake_id,))
    conn.execute("DELETE FROM mistake_tag_map WHERE mistake_id = ?", (mistake_id,))
    conn.execute("DELETE FROM mistakes WHERE id = ?", (mistake_id,))
    conn.commit()
    if old_images:
        remove_image_files(old_images)
    return True


def batch_mistakes(
    conn: sqlite3.Connection,
    ids: List[int],
    action: str,
    source_type: str = "other",
    source_year: str = "",
    source_name: str = "",
) -> int:
    """批量暂停、恢复、删除或修改来源分类，返回处理条数。"""
    ids = [int(item) for item in ids if str(item).strip().isdigit()]
    if not ids:
        raise ValueError("请选择要处理的错题")
    placeholders = ", ".join("?" for _ in ids)

    if action == "delete":
        conn.execute(
            f"DELETE FROM solution_grades WHERE mistake_id IN ({placeholders})",
            ids,
        )
        conn.execute(
            f"DELETE FROM review_records WHERE mistake_id IN ({placeholders})",
            ids,
        )
        conn.execute(
            f"DELETE FROM mistake_tag_map WHERE mistake_id IN ({placeholders})",
            ids,
        )
        cur = conn.execute(
            f"DELETE FROM mistakes WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return cur.rowcount

    if action in ("pause", "resume"):
        cur = conn.execute(
            f"UPDATE mistakes SET review_paused = ? WHERE id IN ({placeholders})",
            (1 if action == "pause" else 0, *ids),
        )
        conn.commit()
        return cur.rowcount

    if action == "source_type":
        source_type = validate_source_type(source_type)
        source_year = source_year.strip()
        source_name = source_name.strip()
        source_issue = validate_source_requirements(
            source_type,
            source_year,
            source_name,
        )
        if source_issue:
            raise ValueError(source_issue)
        cur = conn.execute(
            f"UPDATE mistakes SET source_type = ?, source_year = ?, source_name = ? "
            f"WHERE id IN ({placeholders})",
            (source_type, source_year, source_name, *ids),
        )
        conn.commit()
        return cur.rowcount

    raise ValueError("批量操作类型不支持")
