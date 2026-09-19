"""巡检 data/images 里没人引用的图片，默认只报告，加 --apply 才删。

为什么需要它：
    删错题时配图是「先删行、再删文件」，任何一步没走到（历史 bug、进程被杀、
    手工改库）都会留下孤儿文件。这些文件不占多少磁盘，但**内容仍然可以通过
    /images/<name> 直接访问** —— 已删除错题的截图留在服务器上才是真问题。

为什么默认 dry-run：
    误删错题配图不可恢复（原图只有这一份，而且**自动备份只备份数据库、不备份图片
    目录**）。所以脚本只列出清单，要真删必须显式 --apply，并给出 --keep-days
    保护刚生成还没入库的文件。

判定口径不在这里：全部在 `backend/app/services/integrity_service.py`，
`GET /api/system/integrity`（只读体检页）与本脚本共用同一份。
两边各写一套迟早漂移成"页面说干净、脚本说要删 102 张"。

用法：
    python scripts/clean_orphan_images.py                # 只报告
    python scripts/clean_orphan_images.py --apply        # 报告并删除（含缩略图）
    python scripts/clean_orphan_images.py --apply --keep-days 0
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services import integrity_service  # noqa: E402


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

    # 只读连接：巡检不该有任何写库的机会
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        report = integrity_service.scan(conn, images_dir, keep_days=args.keep_days, limit=10**9)
    finally:
        conn.close()

    orphans = [images_dir / item["rel"] for item in report["orphans"]]
    print(
        f"库内引用 {report['referenced']} 张，扫描到孤儿 {report['orphan_total']} 个"
        f" / {report['orphan_bytes'] / 1e6:.1f} MB"
    )
    if report["protected_recent"]:
        print(
            f"  （另有 {report['protected_recent']} 个文件在 {args.keep_days} 天保护期内，未计入）"
        )
    for path in orphans:
        print(f"  {'删除' if args.apply else '待删'} {path.relative_to(args.data_dir)}")

    if report["missing_total"]:
        print(f"提示：{report['missing_total']} 条记录指向已经不存在的图片（缺图，不是孤儿）")

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
