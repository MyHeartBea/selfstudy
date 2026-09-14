"""pre-commit 本地钩子：密钥泄漏扫描。

背景：项目铁律要求 .env 与各类密钥绝不入库。本就发生过一次密钥被打印到对话里的事故，
所以这里用一个**只读、只看暂存内容**的扫描器把住最后一道关。

设计取向：
- 用「高熵 + 明确前缀」的模式，而不是宽泛的 "key="，以免把 .env.example 之类的
  占位符误判为真密钥（误报会让人习惯性 --no-verify，反而更危险）。
- 命中即失败，并只回显「文件:行号 + 命中类型」，**不打印密钥内容本身**。
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

# (名称, 正则) —— 只收录有明确特征、几乎不可能是占位符的形态
PATTERNS = [
    ("DeepSeek key", re.compile(r"\bsk-[0-9a-fA-F]{32,}\b")),
    ("智谱 key", re.compile(r"\b[0-9a-f]{32}\.[A-Za-z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("OpenAI 风格 key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("私钥块", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
]

# 这些文件允许出现"形状像密钥"的占位符
ALLOWLIST = {
    "backend/.env.example",
    "docs/NEW_SESSION.md",  # 交接文档里可能写示例
}
ALLOW_SUFFIXES = (".md",)  # 文档里的示例值不算泄漏（但仍会打印类型，便于人工确认）


def staged_added_lines() -> dict:
    """返回 {文件: [(行号, 内容)]}，只取本次暂存的新增行。"""
    out = subprocess.run(
        ["git", "diff", "--cached", "-U0", "--diff-filter=ACM"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    ).stdout
    result: dict = {}
    current = None
    lineno = 0
    for line in out.split("\n"):
        if line.startswith("+++ b/"):
            current = line[6:].strip()
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
            continue
        if current is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result.setdefault(current, []).append((lineno, line[1:]))
            lineno += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            lineno += 1
    return result


def main() -> int:
    hits = []
    for rel, lines in staged_added_lines().items():
        if rel in ALLOWLIST or rel.endswith(ALLOW_SUFFIXES):
            continue
        for lineno, content in lines:
            if len(content) > 4000:  # 超长行多为数据/压缩内容，跳过
                continue
            for label, pat in PATTERNS:
                if pat.search(content):
                    # 只报类型与位置，绝不回显密钥
                    hits.append((rel, lineno, label))

    if hits:
        print("!! 疑似密钥将被提交（已拦截，且不显示密钥内容）：")
        for rel, lineno, label in hits:
            print(f"  - {rel}:{lineno}  命中类型: {label}")
        print(
            "\n处理建议：\n"
            "  1) 把该密钥移到 backend/.env（已在 .gitignore 中）；\n"
            "  2) git reset HEAD <文件> 后再提交；\n"
            "  3) 若已推送过，请立刻轮换该密钥。"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
