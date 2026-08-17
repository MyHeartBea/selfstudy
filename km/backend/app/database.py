"""SQLite 连接与数据库初始化。"""

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.config import settings
from app.models.tables import TABLES_DDL
from app.seed_data import seed_database, seed_formula_data, seed_subject_profiles
from app.services.ai_service import _wrap_math
from app.services.knowledge_service import canonical_tags


def get_connection() -> sqlite3.Connection:
    """打开一个新的 SQLite 连接，每个请求独立使用。"""
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def local_day_bounds_utc() -> tuple:
    """返回本地今天在 UTC 中的起止时间（用于查询今日记录）。"""
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%d %H:%M:%S"
    return (
        start.astimezone(timezone.utc).strftime(fmt),
        end.astimezone(timezone.utc).strftime(fmt),
    )


def backup_database() -> None:
    """启动前自动备份现有数据库，防止升级或迁移造成数据丢失。"""
    if not settings.DB_PATH.exists():
        return
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.BACKUP_DIR / f"kaoyan_mistakes_{stamp}.db"

    source = sqlite3.connect(settings.DB_PATH)
    target = sqlite3.connect(dest)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()

    backups = sorted(settings.BACKUP_DIR.glob("kaoyan_mistakes_*.db"))
    for old in backups[: -settings.MAX_BACKUPS]:
        old.unlink(missing_ok=True)


def init_database() -> None:
    """初始化表结构；只在数据库文件首次创建时写入演示数据。"""
    first_start = not settings.DB_PATH.exists()
    if not first_start:
        backup_database()

    conn = get_connection()
    try:
        conn.executescript(TABLES_DDL)
        migrate_database(conn)
        if first_start:
            seed_database(conn)
        else:
            seed_subject_profiles(conn)
        seed_formula_data(conn)
        conn.commit()
    finally:
        conn.close()


# 数据迁移版本：每次全表扫描式迁移执行后+1，避免每次启动重复扫描
MIGRATION_VERSION = 4


def _get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)",
        (key, value),
    )


def migrate_database(conn: sqlite3.Connection) -> None:
    """为旧数据库补充新字段，避免删库。"""
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(mistakes)").fetchall()
    }
    additions = {
        "question_type": "TEXT DEFAULT 'choice'",
        "answer_aliases": "TEXT",
        "difficulty_points": "TEXT",
        "review_count": "INTEGER DEFAULT 0",
        "wrong_count": "INTEGER DEFAULT 0",
        "mastery_level": "INTEGER DEFAULT 0",
        "last_reviewed_at": "DATETIME",
        "next_review_at": "DATETIME",
        "review_paused": "INTEGER DEFAULT 0",
        "source_type": "TEXT DEFAULT ''",
        "source_year": "TEXT DEFAULT ''",
        "source_name": "TEXT DEFAULT ''",
        "images": "TEXT",
    }
    for column, ddl in additions.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE mistakes ADD COLUMN {column} {ddl}")

    review_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(review_records)").fetchall()
    }
    if "user_answer" not in review_columns:
        conn.execute("ALTER TABLE review_records ADD COLUMN user_answer TEXT")

    knowledge_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(knowledge_base)").fetchall()
    }
    if "related_tags" not in knowledge_columns:
        conn.execute("ALTER TABLE knowledge_base ADD COLUMN related_tags TEXT")

    grade_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(solution_grades)").fetchall()
    }
    for column in ("errors", "strengths", "solution", "alternate_methods"):
        if column not in grade_columns:
            conn.execute(f"ALTER TABLE solution_grades ADD COLUMN {column} TEXT")

    _ensure_math_categories(conn)
    _ensure_english_categories(conn)

    # 以下全表扫描式迁移仅在版本升级时执行一次
    try:
        migrated_version = int(_get_meta(conn, "migration_version") or 0)
    except (TypeError, ValueError):
        migrated_version = 0
    if migrated_version >= MIGRATION_VERSION:
        return

    _classify_existing_sources(conn)

    # 统一已有数据的知识点标签命名，保证检索一致
    for row in conn.execute("SELECT id, knowledge_tags FROM mistakes").fetchall():
        raw = row["knowledge_tags"] or ""
        tags = canonical_tags([tag.strip() for tag in raw.split(",") if tag.strip()])
        joined = ",".join(tags)
        if joined != raw:
            conn.execute(
                "UPDATE mistakes SET knowledge_tags = ? WHERE id = ?",
                (joined, row["id"]),
            )
    for row in conn.execute("SELECT id, tag_name FROM knowledge_base").fetchall():
        raw = (row["tag_name"] or "").strip()
        if not raw:
            continue
        canonical = canonical_tags([raw])[0]
        if canonical == raw:
            continue
        existing = conn.execute(
            "SELECT id FROM knowledge_base WHERE tag_name = ? COLLATE NOCASE AND id != ?",
            (canonical, row["id"]),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM knowledge_base WHERE id = ?", (row["id"],))
        else:
            conn.execute(
                "UPDATE knowledge_base SET tag_name = ? WHERE id = ?",
                (canonical, row["id"]),
            )
    _normalize_existing_math(conn)
    _rebuild_mistake_tag_map(conn)
    _set_meta(conn, "migration_version", str(MIGRATION_VERSION))


MATH_FIELDS = (
    ("mistakes", "question"),
    ("mistakes", "option_a"),
    ("mistakes", "option_b"),
    ("mistakes", "option_c"),
    ("mistakes", "option_d"),
    ("mistakes", "correct_answer"),
    ("mistakes", "analysis"),
    ("mistakes", "difficulty_points"),
    ("mistakes", "approach"),
    ("knowledge_base", "summary"),
    ("formula_items", "title"),
    ("formula_items", "content"),
)


def _normalize_existing_math(conn: sqlite3.Connection) -> None:
    """清理历史数据中残留/错位的 $，统一公式表述。"""
    for table, column in MATH_FIELDS:
        rows = conn.execute(
            f"SELECT id, {column} AS value FROM {table}"
        ).fetchall()
        for row in rows:
            value = row["value"] or ""
            cleaned = _wrap_math(value)
            if cleaned != value:
                conn.execute(
                    f"UPDATE {table} SET {column} = ? WHERE id = ?",
                    (cleaned, row["id"]),
                )


def _ensure_math_categories(conn: sqlite3.Connection) -> None:
    """为旧数据库补充数学二级科目：高等数学、线性代数。"""
    # 全新数据库此时 subjects 尚未播种（seed 在 migrate 之后执行），跳过避免外键失败
    subject_count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    if subject_count == 0:
        return
    existing = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sub_subjects WHERE subject_id = 3"
        ).fetchall()
    }
    added_high_math = False
    if "高等数学" not in existing:
        conn.execute(
            "INSERT INTO sub_subjects (subject_id, name) VALUES (3, '高等数学')"
        )
        added_high_math = True
    if "线性代数" not in existing:
        conn.execute(
            "INSERT INTO sub_subjects (subject_id, name) VALUES (3, '线性代数')"
        )

    if added_high_math:
        row = conn.execute(
            "SELECT id FROM sub_subjects WHERE subject_id = 3 AND name = '高等数学'"
        ).fetchone()
        if row is not None:
            high_id = row["id"]
            conn.execute(
                "UPDATE mistakes SET sub_subject_id = ? "
                "WHERE subject_id = 3 AND sub_subject_id IS NULL",
                (high_id,),
            )
            conn.execute(
                "UPDATE knowledge_base SET sub_subject_id = ? "
                "WHERE subject_id = 3 AND sub_subject_id IS NULL",
                (high_id,),
            )


def _ensure_english_categories(conn: sqlite3.Connection) -> None:
    """为旧数据库补充英语二二级科目：完形/阅读/新题型/翻译/写作/词汇语法。"""
    # 全新数据库此时 subjects 尚未播种（seed 在 migrate 之后执行），跳过避免外键失败
    subject_count = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    if subject_count == 0:
        return
    existing = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sub_subjects WHERE subject_id = 2"
        ).fetchall()
    }
    for sub_id, name in (
        (7, "完形填空"),
        (8, "阅读理解"),
        (9, "新题型"),
        (10, "翻译"),
        (11, "写作"),
        (12, "词汇与语法"),
    ):
        if name not in existing:
            conn.execute(
                "INSERT INTO sub_subjects (id, subject_id, name) VALUES (?, 2, ?)",
                (sub_id, name),
            )


def _classify_existing_sources(conn: sqlite3.Connection) -> None:
    """根据来源备注为旧错题补充分类，默认归为其他。"""
    conn.execute(
        "UPDATE mistakes SET source_type = 'other' WHERE source_type = 'self'"
    )
    conn.execute(
        "UPDATE mistakes SET source_type = 'real_exam' "
        "WHERE source_type = '' AND source LIKE '%真题%'"
    )
    conn.execute(
        "UPDATE mistakes SET source_type = 'mock' "
        "WHERE source_type = '' AND source LIKE '%模拟%'"
    )
    conn.execute(
        "UPDATE mistakes SET source_type = 'other' WHERE source_type = ''"
    )
    rows = conn.execute(
        "SELECT id, source FROM mistakes "
        "WHERE source_type IN ('real_exam', 'mock') AND source_year = ''"
    ).fetchall()
    for row in rows:
        match = re.search(r"(19|20)\d{2}", row["source"] or "")
        if match:
            conn.execute(
                "UPDATE mistakes SET source_year = ? WHERE id = ?",
                (match.group(0), row["id"]),
            )


def _rebuild_mistake_tag_map(conn: sqlite3.Connection) -> None:
    """从 mistakes.knowledge_tags 全量重建 mistake_tag_map（迁移用，幂等）。"""
    conn.execute("DELETE FROM mistake_tag_map")
    rows = conn.execute("SELECT id, knowledge_tags FROM mistakes").fetchall()
    for row in rows:
        tags = [t.strip() for t in (row["knowledge_tags"] or "").split(",") if t.strip()]
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO mistake_tag_map (mistake_id, tag) VALUES (?, ?)",
                (row["id"], tag),
            )


def sync_mistake_tags(conn: sqlite3.Connection, mistake_id: int, tags) -> None:
    """错题保存/更新后同步维护标签关联表（先清后插）。"""
    conn.execute("DELETE FROM mistake_tag_map WHERE mistake_id = ?", (mistake_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO mistake_tag_map (mistake_id, tag) VALUES (?, ?)",
            (mistake_id, tag),
        )


def mistake_tag_condition(alias: str = "m", column: str = "id") -> str:
    """生成按标签检索的 EXISTS 条件（走 mistake_tag_map 索引）。

    返回形如 "EXISTS (SELECT 1 FROM mistake_tag_map mt WHERE mt.mistake_id = m.id AND mt.tag = ?)"。
    """
    return (
        f"EXISTS (SELECT 1 FROM mistake_tag_map mt "
        f"WHERE mt.mistake_id = {alias}.{column} AND mt.tag = ?)"
    )


def normalize_tags(value) -> List[str]:
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


def mistake_to_dict(row: sqlite3.Row) -> dict:
    """将错题行转为字典，并把标签字符串还原为数组。"""
    import json as _json

    data = dict(row)
    tags = data.get("knowledge_tags") or ""
    data["knowledge_tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    aliases = data.get("answer_aliases") or ""
    data["answer_aliases"] = [a.strip() for a in aliases.split(";;") if a.strip()]
    raw_images = data.get("images") or ""
    if raw_images:
        try:
            data["images"] = _json.loads(raw_images)
        except (TypeError, ValueError):
            data["images"] = []
    else:
        data["images"] = []
    return data


def mistake_field(fields: dict, column: str) -> Optional[object]:
    """根据数据库列名取对应的字段值。"""
    from app.models.tables import MISTAKE_FIELD_KEYS

    return fields[MISTAKE_FIELD_KEYS.get(column, column)]
