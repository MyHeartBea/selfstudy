"""扫描并清除前端源码里的字符图标（emoji / 箭头 / 符号），与 pre-commit 钩子同一规则。

用途：钩子只在**暂存的新增行**上检查，但当文件里本来就有残留（或钩子规则刚加强时），
需要一个能一次扫全量并直接修的入口。

用法：
  python scripts/strip_chars.py            # 只报告（默认）
  python scripts/strip_chars.py --fix      # 把命中的字符替换成 '-' 后写回
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# **默认只扫 v3**。v2 是正在使用的线上版本，不在 v3 重构范围内，脚本无权改它。
# 本次开发中曾因为把 v2 也纳入扫描而误改 21 个 v2 文件（已全部 git checkout 回退）。
# 如确实要动 v2，必须显式加 --include-v2，让操作者自己确认。
SCOPES = ('frontend-v3/src',)
V2_SCOPE = 'frontend/src'
SUFFIXES = {'.vue', '.js', '.css', '.html'}

# 与 scripts/preflight_check.py 的 EMOJI_RE 保持一致
CHAR_RE = re.compile(
    '[\U0001f000-\U0001faff'  # 表情与象形
    '\u2190-\u21ff'  # 箭头
    '\u2600-\u27bf'  # 各类符号与装饰
    '\u2b00-\u2bff'  # 杂项符号与箭头
    '\ufe0f]'  # 变体选择符
)


def main() -> int:
    ap = argparse.ArgumentParser(description='扫描/清除前端源码里的字符图标')
    ap.add_argument('--fix', action='store_true', help='把命中的字符替换为 -')
    ap.add_argument(
        '--include-v2',
        action='store_true',
        help='同时扫描 v2（frontend/src）。默认不扫：v2 是线上在用版本，不在 v3 重构范围内',
    )
    args = ap.parse_args()

    scopes = SCOPES + ((V2_SCOPE,) if args.include_v2 else ())

    hits = []
    for scope in scopes:
        root = REPO_ROOT / scope
        if not root.is_dir():
            continue
        for path in root.rglob('*'):
            if path.suffix.lower() not in SUFFIXES:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.split('\n'), 1):
                m = CHAR_RE.search(line)
                if m:
                    hits.append((path, i, ord(m.group())))

    if not hits:
        print('未发现字符图标')
        return 0

    for path, line, code in hits:
        print(f'{path.relative_to(REPO_ROOT)}:{line}: U+{code:04X}')

    if not args.fix:
        print(f'\n共 {len(hits)} 处（加 --fix 可直接清除）')
        return 1

    # 按文件聚合后整份重写，避免多次读写
    by_file: dict[Path, str] = {}
    for path, _line, _code in hits:
        if path not in by_file:
            by_file[path] = path.read_text(encoding='utf-8')
    for path, text in by_file.items():
        path.write_text(CHAR_RE.sub('-', text), encoding='utf-8')
        print(f'已清除: {path.relative_to(REPO_ROOT)}')
    print(f'\n处理 {len(hits)} 处，涉及 {len(by_file)} 个文件')
    return 0


if __name__ == '__main__':
    sys.exit(main())
