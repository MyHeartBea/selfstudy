"""性能预算：检查 v3 构建产物的体积，超过阈值即失败。

为什么要这个（而不是只看构建警告）：
    `chunkSizeWarningLimit` 只打印警告，CI 里没人看；等页面变慢时已经晚了。
    这里把"首屏必须多小、单个懒加载块必须多小"变成**可执行断言**。

首屏怎么判定（踩过的坑）：
    起初用"文件名以 index- 开头"来认定入口，结果把 vite 自动拆出的
    3KB 小 chunk（也叫 index-xxxx.js）也算进首屏。正确做法是**以 dist/index.html
    实际引用的 script/link 为准** —— 那才是首次打开真正要下载的东西。

用法：
    python scripts/check_bundle_budget.py
    python scripts/check_bundle_budget.py --json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / 'frontend-v3' / 'dist'

# ── 预算（KB，压缩前；gzip 后约为 1/3）────────────────────────────────
BUDGET_FIRST_SCREEN_KB = 240.0
BUDGET_SINGLE_CHUNK_KB = 320.0
# KaTeX 是公式页专用懒加载块，允许更大，但同样有上限
BUDGET_LAZY_EXCEPTIONS_KB = {'katex': 420.0}


def kb(path: Path) -> float:
    return path.stat().st_size / 1024


def entry_assets(index_html: Path) -> list[Path]:
    """从 index.html 里解析出真正被首屏引用的资源。"""
    html = index_html.read_text(encoding='utf-8', errors='replace')
    refs = set()
    for m in re.finditer(r'(?:src|href)="([^"]+)"', html):
        url = m.group(1)
        if url.startswith('http') or url.startswith('data:'):
            continue
        name = url.split('/')[-1].split('?')[0]
        if name.endswith('.js') or name.endswith('.css'):
            refs.add(name)
    out = []
    for name in sorted(refs):
        p = DIST / 'assets' / name
        if p.is_file():
            out.append(p)
    return out


def main() -> int:
    as_json = '--json' in sys.argv

    index_html = DIST / 'index.html'
    if not index_html.is_file():
        print(f'跳过：{index_html} 不存在（先跑 npm run build）')
        return 0

    assets = [p for p in DIST.glob('assets/*') if p.suffix in ('.js', '.css')]
    if not assets:
        print('跳过：dist/assets 里没有 js/css')
        return 0

    first = entry_assets(index_html)
    # vendor 与入口同属首屏关键路径
    first += [p for p in assets if p.name.startswith('vendor-') and p not in first]
    first_kb = sum(kb(p) for p in first)

    problems: list[str] = []
    if not first:
        problems.append('没能从 index.html 解析出首屏资源（模板结构可能变了，检查本脚本的解析）')
    if first_kb > BUDGET_FIRST_SCREEN_KB:
        problems.append(
            f'首屏 {first_kb:.1f} KB 超过预算 {BUDGET_FIRST_SCREEN_KB:.0f} KB'
            f'（{" + ".join(f"{p.name}={kb(p):.0f}" for p in first)}）'
        )

    for p in assets:
        limit = BUDGET_SINGLE_CHUNK_KB
        for prefix, cap in BUDGET_LAZY_EXCEPTIONS_KB.items():
            if p.name.startswith(prefix):
                limit = cap
        if kb(p) > limit:
            problems.append(f'单块 {p.name} = {kb(p):.1f} KB 超过上限 {limit:.0f} KB')

    report = {
        'firstScreen': [{'name': p.name, 'kb': round(kb(p), 1)} for p in first],
        'firstScreenKB': round(first_kb, 1),
        'firstScreenBudgetKB': BUDGET_FIRST_SCREEN_KB,
        'chunkCount': len(assets),
        'largest': [
            {'name': p.name, 'kb': round(kb(p), 1)}
            for p in sorted(assets, key=kb, reverse=True)[:5]
        ],
        'problems': problems,
    }

    if as_json:
        # --json 只输出纯 JSON：之前同时打印人类摘要，导致消费方（verify_requirements）
        # 无法直接 json.loads，只能靠找 '{' 猜边界 —— 那是脆弱的接口。
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if problems else 0

    print(f'首屏合计 {first_kb:.1f} KB / 预算 {BUDGET_FIRST_SCREEN_KB:.0f} KB')
    print('  组成: ' + ', '.join(f'{p.name} {kb(p):.0f}KB' for p in first))
    print(f'块总数 {len(assets)}（懒加载块不计入首屏）')

    if problems:
        print('\n性能预算未通过：')
        for p in problems:
            print('  -', p)
        return 1

    print('\n结论: 性能预算通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
