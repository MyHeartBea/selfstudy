"""SQLite 连接与数据库初始化。"""

import logging
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.models.tables import TABLES_DDL
from app.seed_data import seed_database, seed_formula_data, seed_subject_profiles
from app.services.ai_service import _wrap_math
from app.services.knowledge_service import canonical_tags

logger = logging.getLogger("kaoyan")


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


def snapshot_database(label: str = "") -> Optional[str]:
    """按需打一份数据快照（导入/批量操作前的"后悔药"）。

    与启动备份共用 BACKUP_DIR，但文件名带 label 便于识别来源，例如
    `kaoyan_mistakes_20260910_193000_before-import.db`。返回快照文件名，失败返回 None。
    快照不会随 MAX_BACKUPS 之外的清理被误删（清理按名字排序，近期的总是保留）。

    失败必须留 ERROR 日志：调用方拿到 None 只是少了一份回滚点，
    静默返回会让"批量删除/导入前已备份"这句话变成假的（响应文案要按 None 降级）。
    """
    if not settings.DB_PATH.exists():
        return None
    try:
        settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(ch for ch in str(label or "") if ch.isalnum() or ch in "-_")
        name = f"kaoyan_mistakes_{stamp}" + (f"_{safe}" if safe else "") + ".db"
        dest = settings.BACKUP_DIR / name

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
        return name
    except Exception:
        logger.exception("数据快照创建失败（label=%s）", label)
        return None


def snapshot_label(name: str) -> str:
    """从快照文件名里取出来源标记（`before-import` / `manual` / …）。

    启动自动备份没有标记，返回空串 —— 前端要把它显示成"启动自动备份"，
    不能显示成一个空白格（空白看起来像数据坏了）。
    """
    stem = re.sub(r"^kaoyan_mistakes_|\.db$", "", str(name or ""))
    parts = stem.split("_", 2)
    return parts[2] if len(parts) > 2 else ""


def list_snapshots(limit: int = 20) -> List[dict]:
    """列出最近的快照（供前端"数据安全"面板展示）。"""
    if not settings.BACKUP_DIR.exists():
        return []
    files = sorted(
        settings.BACKUP_DIR.glob("kaoyan_mistakes_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]
    return [
        {
            "name": p.name,
            "label": snapshot_label(p.name),
            "size_kb": round(p.stat().st_size / 1024, 1),
            "created_at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for p in files
    ]


# 快照文件名由本模块自己生成，回滚时按这个名字反向校验 —— 一个能整库覆盖当前数据的
# 入口如果接受任意字符串，就等于把 BACKUP_DIR 变成了"读哪个文件都行"的口子。
SNAPSHOT_NAME_RE = re.compile(r"^kaoyan_mistakes_\d{8}_\d{6}(?:_[A-Za-z0-9_\-]{1,40})?\.db$")

# 回滚后给页面用来"数一数对不对得上"的表：都是各页面的主数据来源，
# 数量对不对是判断"这份快照是不是我要的那一次"最直接的证据。
SNAPSHOT_TABLES = ("mistakes", "review_records", "knowledge_base", "vocab_items", "exam_papers")

# 整库覆盖是全站唯一"一步毁掉当前现场"的操作。连接虽是每个请求现开，但真题后台
# 拆题在本进程里长期写库，所以要在进程内串行；单用户场景不需要跨进程锁。
_restore_lock = threading.Lock()


def _snapshot_path(name: str) -> Path:
    """把快照文件名换成一个确定落在 BACKUP_DIR 里的路径。"""
    if not SNAPSHOT_NAME_RE.match(str(name or "")):
        raise ValueError("快照文件名不合法")
    path = (settings.BACKUP_DIR / name).resolve()
    if path.parent != settings.BACKUP_DIR.resolve():
        raise ValueError("快照路径越出了备份目录")
    return path


def _table_counts(conn: sqlite3.Connection) -> dict:
    """各主表的行数；老快照里可能还没有某张表，那种记成 None 而不是 0。"""
    counts = {}
    for table in SNAPSHOT_TABLES:
        try:
            counts[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
        except sqlite3.Error:
            counts[table] = None
    return counts


def restore_snapshot(name: str) -> dict:
    """把数据库整库回滚到某一份快照（**就地覆盖当前库**，不替换文件）。

    为什么就地覆盖而不是 `os.replace`：换文件时，本进程里长期持有的连接（后台拆题
    流水线）会继续写在已被换掉的那个句柄上，表现为"回滚完过了一会儿又变回去"。
    SQLite 的 backup API 在目标库上是一个事务，别的连接要么看到旧数据要么看到新数据，
    不会看到半份。

    顺序刻意如此：先验快照可用，再给"当前现场"打反悔快照，反悔快照打不出来就中止。
    任何一步失败都抛异常给调用方转成明确响应 —— 这条路径不许静默。

    注意：**快照只含数据库，不含图片文件**，回滚不会（也回不了）任何配图。
    """
    path = _snapshot_path(name)
    if not path.exists():
        raise FileNotFoundError(f"找不到快照：{name}")

    with _restore_lock:
        # 1. 先验快照读得开、且确实是本系统的库（截断过的 / 手工放进去的不算少见）。
        #    验完**立刻关句柄**：Windows 上被打开的文件删不掉，而下一步的清理正好可能
        #    要删它（实测 WinError 32），到时错误信息会指向"反悔点失败"这种误导结论。
        source = sqlite3.connect(path)
        source.row_factory = sqlite3.Row
        try:
            if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("快照文件不完整（quick_check 未通过），已中止")
            if not source.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mistakes'"
            ).fetchone():
                raise RuntimeError("快照里没有 mistakes 表，不是本系统的数据库备份")
        finally:
            source.close()

        # 2. 先给当前现场留一份，才允许覆盖
        guard = snapshot_database("before-restore")
        if not guard:
            raise RuntimeError("回滚前的现场快照失败，已中止（没有反悔点就不能覆盖当前库）")

        # snapshot_database() 会按 MAX_BACKUPS 清掉最旧的一份 —— 若用户挑的正好是
        # 最旧那一份，它此刻已经不存在了。少了这道复查，下面的 connect 会**凭空建一个
        # 空库**并把当前数据覆盖成空白（一次静默的全库清空，本项目最不能容忍的那种）。
        if not path.exists():
            raise RuntimeError("该快照在留下回滚点时被保留份数限制清理掉了，请选较新的一份快照")

        before_conn = get_connection()
        try:
            before = _table_counts(before_conn)
        finally:
            before_conn.close()

        # 3. 就地覆盖当前库
        source = sqlite3.connect(path)
        source.row_factory = sqlite3.Row
        try:
            target = get_connection()
            try:
                with target:
                    source.backup(target)
                # 4. 快照可能比当前代码旧（少表少列）。补一遍幂等 DDL 与迁移，
                #    否则回滚到 v8 那份会让 /papers 一类页面打到 500，且要重启才自愈。
                target.executescript(TABLES_DDL)
                migrate_database(target)
                target.commit()
                after = _table_counts(target)
            finally:
                target.close()
        finally:
            source.close()

    logger.warning("数据库已回滚到快照 %s（回滚前的现场另存为 %s）", name, guard)
    return {
        "name": name,
        "safety_snapshot": guard,
        "tables_before": before,
        "tables_after": after,
    }


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
MIGRATION_VERSION = 10


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
        row["name"] for row in conn.execute("PRAGMA table_info(mistakes)").fetchall()
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
        "starred": "INTEGER DEFAULT 0",
        "source_type": "TEXT DEFAULT ''",
        "source_year": "TEXT DEFAULT ''",
        "source_name": "TEXT DEFAULT ''",
        "images": "TEXT",
        "passage_text": "TEXT",
        "passage_translation": "TEXT",
        "english_sentences": "TEXT",
        "english_phrases": "TEXT",
        "english_words": "TEXT",
        "english_questions": "TEXT",
        # SM-2 简化版自适应调度（v6）
        "ease_factor": "REAL DEFAULT 2.5",
        "last_interval": "INTEGER DEFAULT 0",
    }
    for column, ddl in additions.items():
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE mistakes ADD COLUMN {column} {ddl}")

    review_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(review_records)").fetchall()
    }
    if "user_answer" not in review_columns:
        conn.execute("ALTER TABLE review_records ADD COLUMN user_answer TEXT")

    knowledge_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(knowledge_base)").fetchall()
    }
    if "related_tags" not in knowledge_columns:
        conn.execute("ALTER TABLE knowledge_base ADD COLUMN related_tags TEXT")

    grade_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(solution_grades)").fetchall()
    }
    for column in ("errors", "strengths", "solution", "alternate_methods"):
        if column not in grade_columns:
            conn.execute(f"ALTER TABLE solution_grades ADD COLUMN {column} TEXT")

    # 科目类型：math/english/politics/cs/generic，驱动前端按科目定制题型与交互
    subject_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(subjects)").fetchall()
    }
    if "kind" not in subject_columns:
        conn.execute("ALTER TABLE subjects ADD COLUMN kind TEXT DEFAULT ''")

    # 生词本：单词/词语分类
    vocab_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(vocab_items)").fetchall()
    }
    if "kind" not in vocab_columns:
        conn.execute("ALTER TABLE vocab_items ADD COLUMN kind TEXT DEFAULT 'word'")
    # 把含空格的短语归类为 phrase（历史数据默认 word，需回填）
    conn.execute(
        "UPDATE vocab_items SET kind = 'phrase' WHERE kind = 'word' AND TRIM(word) LIKE '% %'"
    )

    # 模考成绩存档表（v7）
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mock_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_year TEXT DEFAULT '',
            total INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            duration_min INTEGER DEFAULT 60,
            used_seconds INTEGER DEFAULT 0,
            created_at DATETIME
        )
        """
    )

    # 真题库（v8）
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exam_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT DEFAULT '',
            year TEXT DEFAULT '',
            title TEXT DEFAULT '',
            source_path TEXT DEFAULT '',
            answer_path TEXT DEFAULT '',
            question_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            status_note TEXT DEFAULT '',
            created_at DATETIME
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exam_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL REFERENCES exam_papers(id) ON DELETE CASCADE,
            no TEXT DEFAULT '',
            section TEXT DEFAULT '',
            question_type TEXT DEFAULT 'choice',
            passage TEXT DEFAULT '',
            question TEXT DEFAULT '',
            option_a TEXT DEFAULT '',
            option_b TEXT DEFAULT '',
            option_c TEXT DEFAULT '',
            option_d TEXT DEFAULT '',
            correct_answer TEXT DEFAULT '',
            analysis TEXT DEFAULT '',
            knowledge_tags TEXT DEFAULT '',
            page_idx INTEGER DEFAULT 0,
            diagram_image TEXT DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_questions_paper ON exam_questions(paper_id)")

    # 英语作文批改存档（v10）：旧库升级补建（新库 DDL 已含，IF NOT EXISTS 幂等）
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS essay_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT DEFAULT 'e2_long',
            prompt_text TEXT DEFAULT '',
            essay_text TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            max_score INTEGER DEFAULT 15,
            result_json TEXT DEFAULT '{}',
            created_at DATETIME
        )
        """
    )
    # 索引一律由 TABLES_DDL 负责（它在 migrate_database 之前先 executescript 一遍，
    # 且每条都是 IF NOT EXISTS / IF EXISTS，对新旧库都幂等）。
    # 这里**不许**再补 CREATE INDEX：v11 把 essay 的 (kind) 换成 (kind, id DESC) 并删旧名，
    # 而本函数在 DDL 之后运行，残留一句旧 DDL 就会把已删的单列索引又建回来。

    _ensure_math_categories(conn)
    _ensure_english_categories(conn)
    _ensure_politics_categories(conn)

    # 以下全表扫描式迁移仅在版本升级时执行一次
    try:
        migrated_version = int(_get_meta(conn, "migration_version") or 0)
    except (TypeError, ValueError):
        migrated_version = 0
    if migrated_version >= MIGRATION_VERSION:
        return

    _classify_existing_sources(conn)
    _infer_subject_kinds(conn)
    _seed_subject_guides(conn)

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

    # v6：按旧阶梯回填上次间隔，存量题从平滑处续接 SM-2 调度（只跑一次）
    conn.execute(
        "UPDATE mistakes SET last_interval = CASE mastery_level "
        "WHEN 1 THEN 1 WHEN 2 THEN 3 WHEN 3 THEN 7 WHEN 4 THEN 15 WHEN 5 THEN 30 "
        "ELSE 0 END "
        "WHERE last_interval IS NULL OR last_interval <= 0"
    )

    # v9：exam_questions 加 页码/题图（旧库升级补列；新库建表已带，跳过）
    _eq_cols = {c["name"] for c in conn.execute("PRAGMA table_info(exam_questions)").fetchall()}
    if "page_idx" not in _eq_cols:
        conn.execute("ALTER TABLE exam_questions ADD COLUMN page_idx INTEGER DEFAULT 0")
    if "diagram_image" not in _eq_cols:
        conn.execute("ALTER TABLE exam_questions ADD COLUMN diagram_image TEXT DEFAULT ''")

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
        rows = conn.execute(f"SELECT id, {column} AS value FROM {table}").fetchall()
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
        for row in conn.execute("SELECT name FROM sub_subjects WHERE subject_id = 3").fetchall()
    }
    added_high_math = False
    if "高等数学" not in existing:
        conn.execute("INSERT INTO sub_subjects (subject_id, name) VALUES (3, '高等数学')")
        added_high_math = True
    if "线性代数" not in existing:
        conn.execute("INSERT INTO sub_subjects (subject_id, name) VALUES (3, '线性代数')")

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
        for row in conn.execute("SELECT name FROM sub_subjects WHERE subject_id = 2").fetchall()
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


def _ensure_politics_categories(conn: sqlite3.Connection) -> None:
    """为政治科目补充子科目：马原/毛中特/史纲/思修/时政。

    subject_id 按 seed 顺序为 1（政治）；仅对名字含"政治"的科目生效，避免硬编码错位。
    """
    rows = conn.execute("SELECT id FROM subjects WHERE name LIKE '%政治%'").fetchall()
    for row in rows:
        politics_id = row["id"]
        existing = {
            item["name"]
            for item in conn.execute(
                "SELECT name FROM sub_subjects WHERE subject_id = ?",
                (politics_id,),
            ).fetchall()
        }
        for name in ("马克思主义基本原理", "毛中特", "史纲", "思修法基", "时政"):
            if name not in existing:
                conn.execute(
                    "INSERT INTO sub_subjects (subject_id, name) VALUES (?, ?)",
                    (politics_id, name),
                )


def _infer_subject_kinds(conn: sqlite3.Connection) -> None:
    """按科目名推断科目类型（仅迁移时执行一次，之后可手工修正）。"""
    rules = (
        ("数学", "math"),
        ("英语", "english"),
        ("政治", "politics"),
        ("408", "cs"),
        ("计算机", "cs"),
    )
    rows = conn.execute("SELECT id, name, kind FROM subjects").fetchall()
    for row in rows:
        if row["kind"]:
            continue
        for keyword, kind in rules:
            if keyword in (row["name"] or ""):
                conn.execute(
                    "UPDATE subjects SET kind = ? WHERE id = ?",
                    (kind, row["id"]),
                )
                break


def _seed_subject_guides(conn: sqlite3.Connection) -> None:
    """为英语/政治写入默认复习指南（仅当档案为空时），数学/408 已有则不动。"""
    guides = {
        "英语": (
            ["词汇滚动记忆", "阅读精读", "长难句拆解", "真题二刷三刷", "作文模板积累"],
            "单词每天快刷不断线（生词本到期即刷）；阅读精做近10-15年真题，做完四件事："
            "查错因、口头翻译全文、摘抄长难句、生词进生词本；完形重点在固定搭配；"
            "翻译对照参考译文自评；作文先背模板再仿写默写，考前掐时间整卷模拟。",
        ),
        "政治": (
            ["选择题拉分", "多选专项", "错题二刷三刷", "时政更新", "分析题背诵"],
            "选择题是拉分关键：题库至少两刷，二刷只刷错题；多选少选错选均不得分，"
            "错题务必标注错因（知识点未记牢/干扰项混淆/漏选）；"
            "按马原重理解、毛中特重框架、史纲重线索推进；"
            "11月起转背诵手册+时政，12月集中背分析题，用「背是为了写」的方法输出。",
        ),
    }
    for keyword, (focus, tips) in guides.items():
        subject = conn.execute(
            "SELECT id FROM subjects WHERE name LIKE ?",
            (f"%{keyword}%",),
        ).fetchone()
        if subject is None:
            continue
        existing = conn.execute(
            "SELECT id FROM subject_profiles WHERE subject_id = ?", (subject["id"],)
        ).fetchone()
        if existing is not None:
            continue
        import json as _json

        conn.execute(
            "INSERT INTO subject_profiles (subject_id, focus_areas, review_tips) VALUES (?, ?, ?)",
            (subject["id"], _json.dumps(focus, ensure_ascii=False), tips),
        )


def _classify_existing_sources(conn: sqlite3.Connection) -> None:
    """根据来源备注为旧错题补充分类，默认归为其他。"""
    conn.execute("UPDATE mistakes SET source_type = 'other' WHERE source_type = 'self'")
    conn.execute(
        "UPDATE mistakes SET source_type = 'real_exam' "
        "WHERE source_type = '' AND source LIKE '%真题%'"
    )
    conn.execute(
        "UPDATE mistakes SET source_type = 'mock' WHERE source_type = '' AND source LIKE '%模拟%'"
    )
    conn.execute("UPDATE mistakes SET source_type = 'other' WHERE source_type = ''")
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

    # 英语整篇精读附加字段（JSON 字符串 → 数组）。
    # 列表查询（LIST_COLUMNS）不含这些列，保持缺席以缩小响应体；其余路径全列输出。
    for column in ("english_sentences", "english_phrases", "english_words", "english_questions"):
        if column not in data:
            continue
        raw = data.get(column) or ""
        if raw:
            try:
                data[column] = _json.loads(raw)
            except (TypeError, ValueError):
                data[column] = []
        else:
            data[column] = []
    return data


def mistake_field(fields: dict, column: str) -> Optional[object]:
    """根据数据库列名取对应的字段值。"""
    from app.models.tables import MISTAKE_FIELD_KEYS

    return fields[MISTAKE_FIELD_KEYS.get(column, column)]
