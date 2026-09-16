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

# 硬性约束（用户明确要求，写进钩子避免靠人记得）：
# 前端源码与样张页面全程禁止 emoji。代理对（surrogate）与常见符号区都算命中。
EMOJI_RE = re.compile(
    "[\U0001f000-\U0001faff"  # 表情、象形、补充符号
    "\u2190-\u21ff"           # 箭头（图标必须用 Lucide，不许用字符箭头）
    "\u2600-\u27bf"           # 各类符号与装饰
    "\u2b00-\u2bff"           # 杂项符号与箭头
    "\ufe0f]"                 # 变体选择符（emoji 呈现）
)
# 只强制约束"我们自己写的前端与文档"，不扫第三方产物
EMOJI_SCOPES = ("frontend-v3/src/", "frontend/src/", "docs/art-direction")


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

    # 3) emoji / 字符图标：前端源码与样张页面禁止（图标统一走 Lucide）
    for rel in files:
        rel_posix = rel.replace("\\", "/")
        if not rel_posix.startswith(EMOJI_SCOPES):
            continue
        p = REPO_ROOT / rel
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.split("\n"), 1):
            m = EMOJI_RE.search(line)
            if m:
                # 不回显上下文（可能落在密钥/长行里），只给位置与码位
                problems.append(
                    f"{rel}:{i}: 出现 emoji / 字符图标 U+{ord(m.group()):04X}（图标请用 Lucide）"
                )

    if problems:
        print("pre-commit 卫生检查未通过：")
        for x in problems:
            print("  -", x)
        print("\n提示：git add 前先修好；行尾空白可用命令批量清理。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
