"""巡检 data/images 里没人引用的图片，默认只报告，加 --apply 才删。

为什么需要它：
    删错题时配图是「先删行、再删文件」，任何一步没走到（历史 bug、进程被杀、
    手工改库）都会留下孤儿文件。这些文件不占多少磁盘，但**内容仍然可以通过
    /images/<name> 直接访问** —— 已删除错题的截图留在服务器上才是真问题。

为什么默认 dry-run：
    误删错题配图不可恢复（原图只有这一份）。所以脚本只列出清单，
    要真删必须显式 --apply，并给出 --keep-days 保护刚生成还没入库的文件。

引用来源目前只有两处（库里带图片列的表就这两个）：
    mistakes.images（JSON 数组）与 exam_questions.diagram_image（单值，图示题的整页原图）。
    只按 mistakes 判定会把真题图示题的原图当成孤儿删掉。新增图片列时要在 REF_SOURCES 登记。

用法：
    python scripts/clean_orphan_images.py                # 只报告
    python scripts/clean_orphan_images.py --apply        # 报告并删除（含缩略图）
    python scripts/clean_orphan_images.py --apply --keep-days 0
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

# (表, 列, 是否 JSON 数组)
REF_SOURCES = (
    ("mistakes", "images", True),
    ("exam_questions", "diagram_image", False),
)


def referenced_names(db_path: Path) -> set[str]:
    """收集库里引用到的图片文件名（取 basename，忽略相对路径前缀）。"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    names: set[str] = set()
    try:
        for table, column, is_json in REF_SOURCES:
            try:
                rows = conn.execute(f"SELECT {column} FROM {table}").fetchall()
            except sqlite3.OperationalError:
                # 老库/测试库里可能还没这张表：跳过而不是让整轮巡检崩掉
                continue
            for (raw,) in rows:
                if raw is None or raw == "":
                    continue
                values = []
                if is_json:
                    try:
                        parsed = json.loads(raw)
                    except (TypeError, ValueError):
                        # 解析不了就保守跳过：宁可漏报也不误删
                        continue
                    values = parsed if isinstance(parsed, list) else [parsed]
                else:
                    values = [raw]
                for value in values:
                    text = str(value or "").replace("\\", "/").strip()
                    if text:
                        names.add(Path(text).name)
    finally:
        conn.close()
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="巡检/清理无人引用的图片文件")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--apply", action="store_true", help="真正删除（默认只报告）")
    parser.add_argument(
        "--keep-days",
        type=float,
        default=1.0,
        help="最近 N 天内生成的文件不算孤儿（可能正在写入流水线里）",
    )
    args = parser.parse_args(argv)

    images_dir = args.data_dir / "images"
    db_path = args.data_dir / "kaoyan_mistakes.db"
    if not images_dir.is_dir() or not db_path.is_file():
        print(f"跳过：找不到 {images_dir} 或 {db_path}", file=sys.stderr)
        return 0

    refs = referenced_names(db_path)
    cutoff = time.time() - args.keep_days * 86400
    # _thumbs/ 与 exam_papers/ 由各自的源文件决定去留，跟随主文件一起处理
    orphans = []
    for path in sorted(images_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            continue
        if path.name in refs:
            continue
        # 缩略图按原名（stem）匹配；主图留下则缩略图也留下
        if "_thumbs" in path.parts and path.stem in {Path(r).stem for r in refs}:
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        orphans.append(path)

    total_bytes = sum(p.stat().st_size for p in orphans)
    print(f"库内引用 {len(refs)} 张，扫描到孤儿 {len(orphans)} 个 / {total_bytes / 1e6:.1f} MB")
    for path in orphans:
        rel = path.relative_to(args.data_dir)
        print(f"  {'删除' if args.apply else '待删'} {rel}")

    if args.apply:
        removed = 0
        for path in orphans:
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                print(f"  失败 {path}: {exc}", file=sys.stderr)
        print(f"已删除 {removed} 个文件")
    elif orphans:
        print("未删除任何文件；确认无误后加 --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
