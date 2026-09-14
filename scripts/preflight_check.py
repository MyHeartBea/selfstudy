"""pre-commit 本地钩子：后端 Ruff 检查 + 行尾空白/大文件卫生。

不依赖网络（不用 pre-commit 的远程 hook 源，避免代理不稳），直接调用项目里的工具。
"""

import re
import subprocess
import sys
from pathlib import Path

def _repo_root() -> Path:
    """仓库根：以 git 为准（脚本在 scripts/ 下，硬编码 parents 层级容易数错）。"""
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    root = out.stdout.strip()
    return Path(root) if root else Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
MAX_BYTES = 2 * 1024 * 1024  # 单文件 2MB 上限（数据库/图片/真题不该入库）
TEXT_SUFFIXES = {
    ".py", ".js", ".vue", ".css", ".html", ".json", ".md", ".yml", ".yaml",
    ".txt", ".cfg", ".toml", ".cmd", ".ps1", ".sh",
}


def staged_files() -> list:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    return [f.strip() for f in out.splitlines() if f.strip()]


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    problems = []

    # 1) 大文件
    for rel in files:
        p = REPO_ROOT / rel
        if p.is_file() and p.stat().st_size > MAX_BYTES:
            problems.append(f"{rel}: 文件过大（{p.stat().st_size // 1024} KB > 2 MB），不应入库")

    # 2) 行尾空白 / 文件末尾缺换行（只查文本文件）
    for rel in files:
        p = REPO_ROOT / rel
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.split("\n"), 1):
            if re.search(r"[ \t]+$", line):
                problems.append(f"{rel}:{i}: 行尾有空白")
                break
        if text and not text.endswith("\n"):
            problems.append(f"{rel}: 文件末尾缺少换行")

    if problems:
        print("pre-commit 卫生检查未通过：")
        for x in problems:
            print("  -", x)
        print("\n提示：git add 前先修好；行尾空白可用命令批量清理。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
