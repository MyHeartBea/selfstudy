"""数据体检（N2）：图片文件与库里引用的一致性，**只读**。

为什么要它：删错题是"先删行、再删文件"，任何一步没走到（历史 bug、进程被杀、手工改库）
都会留下对不上的东西 —— 要么文件没人引用（内容还能通过 /images/<name> 直接访问），
要么行指向一张已经不存在的图（页面上就是一个破图）。这两种都只能靠巡检发现。

**判定口径只有这一份**：`scripts/clean_orphan_images.py` 也 import 这里，不另写一套。
两边各写各的，迟早漂移成"页面说干净、脚本说要删 102 张"，而那正是最需要一致的地方。

本模块不删任何东西（也没有删除函数）；清理仍是脚本的 `--apply`，且默认 dry-run。
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 库里带图片的列就这两个（新增第三处时必须登记在这里，否则新表会把图判成孤儿）。
# (表, 列, 是否 JSON 数组)
IMAGE_REF_SOURCES: Tuple[Tuple[str, str, bool], ...] = (
    ("mistakes", "images", True),
    ("exam_questions", "diagram_image", False),
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def image_references(conn: sqlite3.Connection) -> Tuple[Dict[str, List[str]], int]:
    """库里引用到的图片：`{文件名 basename: ["mistakes#12", ...]}` + 解析不了的行数。

    按 **basename** 归并是因为存进来的形状并不统一：`mistakes.images` 存
    `images/xxx.png`（相对路径），`exam_questions.diagram_image` 存
    `/images/exam_papers/16/p0.webp`（URL）。两边都比 basename，才不会因为前缀
    不同而把同一张图看成两个。

    JSON 解析失败时**保守跳过该行的引用**：少一条引用只会让文件更像孤儿，
    所以这个数要回给调用方看（`unparseable_refs`），不能静默。
    """
    refs: Dict[str, List[str]] = {}
    unparseable = 0
    for table, column, is_json in IMAGE_REF_SOURCES:
        try:
            rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()
        except sqlite3.OperationalError:
            # 老库/测试库里可能还没这张表：跳过而不是让整轮巡检崩掉
            continue
        for row in rows:
            raw = row[1]
            if raw is None or raw == "":
                continue
            if is_json:
                try:
                    parsed = json.loads(raw)
                except (TypeError, ValueError):
                    unparseable += 1
                    continue
                values = parsed if isinstance(parsed, list) else [parsed]
            else:
                values = [raw]
            for value in values:
                text = str(value or "").replace("\\", "/").strip()
                if not text:
                    continue
                locator = f"{table}#{row[0]}"
                bucket = refs.setdefault(Path(text).name, [])
                if locator not in bucket and len(bucket) < 5:
                    bucket.append(locator)
    return refs, unparseable


def _kind_of(path: Path, images_dir: Path) -> str:
    parts = path.relative_to(images_dir).parts
    if "_thumbs" in parts:
        return "thumb"
    if "exam_papers" in parts:
        return "exam_page"
    return "image"


def scan(
    conn: sqlite3.Connection,
    images_dir: Path,
    keep_days: float = 1.0,
    limit: int = 200,
    now: float | None = None,
) -> Dict[str, Any]:
    """一次巡检的全部结论。返回给接口也返回给脚本（同一份判定）。

    `keep_days`：最近 N 天生成的文件不算孤儿 —— 真题拆题是后台流水线，
    图先落盘、`diagram_image` 后写库，中间那几秒会被误判。
    """
    refs, unparseable = image_references(conn)
    empty = {
        "referenced": len(refs),
        "files": 0,
        "bytes_total": 0,
        "orphans": [],
        "orphan_total": 0,
        "orphan_bytes": 0,
        "orphan_truncated": False,
        "protected_recent": 0,
        "missing": [],
        "missing_total": 0,
        "unparseable_refs": unparseable,
        "keep_days": keep_days,
        "images_dir_exists": False,
    }
    if not images_dir.is_dir():
        return empty

    cutoff = (now if now is not None else time.time()) - keep_days * 86400
    existing: set = set()
    orphans: List[Dict[str, Any]] = []
    protected = 0
    files = 0
    bytes_total = 0
    # 主图留下则它的缩略图也留下（缩略图文件名是主图的 stem + .webp）
    ref_stems = {Path(name).stem for name in refs}
    for path in sorted(images_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        files += 1
        try:
            stat = path.stat()
        except OSError:
            continue
        existing.add(path.name)
        bytes_total += stat.st_size
        if path.name in refs:
            continue
        if "_thumbs" in path.parts and path.stem in ref_stems:
            continue
        if stat.st_mtime >= cutoff:
            protected += 1
            continue
        orphans.append(
            {
                "rel": str(path.relative_to(images_dir)).replace("\\", "/"),
                "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "kind": _kind_of(path, images_dir),
            }
        )
    # 大的排前面：想清空间/查隐私时先看值得看的那几张
    orphans.sort(key=lambda item: (-item["size"], item["rel"]))
    missing = [
        {"name": name, "refs": locators}
        for name, locators in sorted(refs.items())
        if name not in existing
    ]
    return {
        "referenced": len(refs),
        "files": files,
        "bytes_total": bytes_total,
        "orphans": orphans[:limit],
        "orphan_total": len(orphans),
        "orphan_bytes": sum(item["size"] for item in orphans),
        "orphan_truncated": len(orphans) > limit,
        "protected_recent": protected,
        "missing": missing[:limit],
        "missing_total": len(missing),
        "unparseable_refs": unparseable,
        "keep_days": keep_days,
        "images_dir_exists": True,
    }


def orphan_paths(conn: sqlite3.Connection, images_dir: Path, keep_days: float = 1.0) -> List[Path]:
    """脚本专用：待删的绝对路径（顺序与页面清单一致，大的在前）。"""
    report = scan(conn, images_dir, keep_days=keep_days, limit=10**9)
    return [images_dir / item["rel"] for item in report["orphans"]]
