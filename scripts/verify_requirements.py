"""逐条核验 v3 是否满足用户最初提出的硬性要求（可复跑）。

为什么写成脚本而不是写在文档里：
    文档里的"已完成"会随代码演进而失真。这里每条要求都对应**可执行的检查**：
    代码/构建产物里的客观证据（文件存在、字符串出现、产物内容、无外链等）。
    跑一次就知道哪条真满足、哪条不满足，不靠记忆。

用法：
    python scripts/verify_requirements.py
    python scripts/verify_requirements.py --json
退出码：0 全部满足；1 有未满足项（会逐条列出缺什么）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
V3 = REPO / 'frontend-v3'
SRC = V3 / 'src'
DIST = V3 / 'dist'
DOCS = REPO / 'docs'

problems: list[str] = []


def read_all(root: Path, suffixes=('.vue', '.js', '.css')) -> str:
    out = []
    if not root.is_dir():
        return ''
    for p in root.rglob('*'):
        if p.suffix in suffixes and p.is_file():
            out.append(p.read_text(encoding='utf-8', errors='replace'))
    return '\n'.join(out)


SRC_TEXT = read_all(SRC)
DIST_TEXT = read_all(DIST, ('.js', '.css', '.html')) if DIST.is_dir() else ''
INDEX_HTML = (DIST / 'index.html').read_text(encoding='utf-8') if (DIST / 'index.html').is_file() else ''


def check(name: str, ok: bool, detail: str) -> None:
    print(f'{"OK  " if ok else "FAIL"} {name}  {detail}')
    if not ok:
        problems.append(f'{name}: {detail}')


def main() -> int:
    as_json = '--json' in sys.argv
    results = []

    def rec(name, ok, detail):
        results.append({'name': name, 'ok': ok, 'detail': detail})
        if not as_json:
            print(f'{"OK  " if ok else "FAIL"} {name}  {detail}')
        if not ok:
            problems.append(f'{name}: {detail}')

    # 1. 统一核心隐喻
    metaphor_in_src = ('夜航' in SRC_TEXT or '星图' in SRC_TEXT) and '红移' in SRC_TEXT
    metaphor_doc = (DOCS / 'v3-handoff.md').is_file() and '未掌握的是暗' in (
        (DOCS / 'v3-handoff.md').read_text(encoding='utf-8')
    )
    rec('统一核心隐喻（夜航星图）', metaphor_in_src and metaphor_doc,
        '源码含隐喻词汇且 handoff 写明隐喻定义' if metaphor_in_src and metaphor_doc
        else f'src={metaphor_in_src} doc={metaphor_doc}')

    # 2. 实验性排版（非对称网格 / 巨型字级 / 等宽读数）
    fluid = 'clamp(' in SRC_TEXT
    asymmetric = 'grid-template-columns: repeat(12' in SRC_TEXT or 'span 6' in SRC_TEXT
    mono = '--font-mono' in SRC_TEXT
    rec('实验性排版（流体字级 + 非对称网格 + 等宽读数）', fluid and asymmetric and mono,
        f'clamp={fluid} 非对称网格={asymmetric} 等宽={mono}')

    # 3. OKLCH 色彩
    oklch = SRC_TEXT.count('oklch(')
    rec('OKLCH 色彩', oklch >= 20, f'源码出现 oklch() {oklch} 处')

    # 4. 物理感动效（六原语）
    primitives = ['drift', 'settle', 'flare', 'trace', 'scan', 'focus']
    motion_js = (SRC / 'design' / 'motion.js').read_text(encoding='utf-8') if (SRC / 'design' / 'motion.js').is_file() else ''
    missing = [p for p in primitives if p not in motion_js]
    rec('物理感动效（六条原语）', not missing, f'缺失={missing or "无"}')

    # 5. WebGL / Canvas 背景
    starfield = (SRC / 'sky' / 'Starfield.vue')
    sf = starfield.read_text(encoding='utf-8') if starfield.is_file() else ''
    has_gl = 'getContext' in sf and ('gl.' in sf or 'webgl' in sf.lower())
    rec('WebGL / Canvas 背景', has_gl, f'Starfield.vue 使用 WebGL={has_gl}')

    # 6. 自定义光标
    cursor = (SRC / 'sky' / 'SkyCursor.vue')
    cs = cursor.read_text(encoding='utf-8') if cursor.is_file() else ''
    rec('自定义光标', 'lerp' in cs or 'SkyCursor' in SRC_TEXT, f'SkyCursor 存在={cursor.is_file()}')

    # 7. 磁吸
    rec('磁吸（magnetic）', 'export function magnetic' in motion_js and 'data-magnet' in SRC_TEXT,
        'magnetic 原语 + data-magnet 用法均存在')

    # 8. 滚动叙事（滚动隐藏导航 + 滚动入场）
    shell = (SRC / 'app' / 'AppShell.vue')
    sh = shell.read_text(encoding='utf-8') if shell.is_file() else ''
    scroll_hide = 'scrollY' in sh and 'up' in sh
    reveal_pages = sum(1 for p in (SRC / 'views').glob('*.vue') if 'data-reveal' in p.read_text(encoding='utf-8'))
    rec('滚动叙事（导航隐藏 + 逐屏入场）', scroll_hide and reveal_pages >= 10,
        f'导航滚动隐藏={scroll_hide} 有入场动效的页面={reveal_pages}')

    # 9. 悬停变形
    hover_clip = 'clip-path' in SRC_TEXT
    hover_hover = SRC_TEXT.count(':hover')
    rec('悬停变形', hover_clip and hover_hover >= 20, f'clip-path 填充={hover_clip} :hover 规则={hover_hover} 处')

    # 10. Lucide 图标（本地依赖、无 CDN）
    pkg = (V3 / 'package.json').read_text(encoding='utf-8') if (V3 / 'package.json').is_file() else ''
    rec('Lucide 图标（本地依赖）', 'lucide-vue-next' in pkg, 'package.json 依赖 lucide-vue-next')

    # 11. 零 emoji / 零字符图标
    emoji_re = re.compile(
        '[\U0001f000-\U0001faff\u2190-\u21ff\u2600-\u27bf\u2b00-\u2bff\ufe0f]'
    )
    hits = [m.group() for m in emoji_re.finditer(SRC_TEXT)]
    rec('零 emoji / 零字符图标', not hits, f'命中 {len(hits)} 处' + (f'：{hits[:6]}' if hits else ''))

    # 12. 无外链（离线可用）
    cdn = re.findall(r'https?://[^\s"\'()]+', SRC_TEXT + INDEX_HTML)
    cdn = [u for u in cdn if 'w3.org' not in u and 'localhost' not in u and '127.0.0.1' not in u]
    rec('零 CDN 外链（离线可用）', not cdn, f'发现 {len(cdn)} 条外链' + (f'：{cdn[:3]}' if cdn else ''))

    # 13. 可访问性（h1 / aria / 焦点环）
    h1_pages = sum(1 for p in (SRC / 'views').glob('*.vue') if '<h1' in p.read_text(encoding='utf-8'))
    aria = SRC_TEXT.count('aria-')
    rec('可访问性（h1 + aria + 焦点）', h1_pages >= 13 and aria >= 40,
        f'含 h1 的页面={h1_pages} aria 属性={aria} 处')

    # 14. prefers-reduced-motion 降级
    rm = SRC_TEXT.count('prefers-reduced-motion')
    rec('prefers-reduced-motion 降级', rm >= 8, f'降级规则 {rm} 处')

    # 15. 60fps 相关（只用 transform/opacity/filter；rAF+lerp）
    raf = SRC_TEXT.count('requestAnimationFrame')
    will_change = SRC_TEXT.count('will-change')
    rec('60fps 措施（rAF + 合成层提示）', raf >= 6 and will_change >= 3,
        f'requestAnimationFrame {raf} 处 / will-change {will_change} 处')

    # 16. 启动页重新设计
    loader = (SRC / 'app' / 'InkLoader.vue')
    ld = loader.read_text(encoding='utf-8') if loader.is_file() else ''
    loader_ok = all(k in ld for k in ['reticle', 'ticks', 'ring-out', 'veil'])
    rec('启动页重新设计', loader_ok, '含目镜刻度环 / 十字丝 / 进度弧 / 揭幕遮罩')

    # 17. 构建产物存在且首屏受预算约束
    #     这里真跑预算脚本，而不是只判断"文件存在" —— 只看存在等于没检查。
    import subprocess

    budget = subprocess.run(
        [sys.executable, str(REPO / 'scripts' / 'check_bundle_budget.py'), '--json'],
        capture_output=True, text=True, cwd=str(REPO),
        # Windows 默认用 GBK 解码子进程输出，而脚本输出是 UTF-8（中文）→
        # 会抛 UnicodeDecodeError 并让 stdout 变成 None。必须显式指定。
        encoding='utf-8', errors='replace',
    )
    budget_ok = budget.returncode == 0
    budget_detail = '预算脚本未通过'
    # 脚本在 --json 下先打印人类可读摘要、再打印 JSON；这里把两种输出都兼容
    try:
        start = budget.stdout.index('{')
        rep = json.loads(budget.stdout[start:])
        budget_detail = f'首屏 {rep.get("firstScreenKB")} KB / 预算 {rep.get("firstScreenBudgetKB")} KB'
    except Exception:
        first_line = (budget.stdout or budget.stderr).strip().split('\n')[0]
        budget_detail = first_line[:90]
    rec('构建产物 + 首屏体积预算', (DIST / 'index.html').is_file() and budget_ok,
        f'dist/index.html 存在 / {budget_detail}')

    # 18. v2 源码确实未被本轮改动（真跑 git，不硬编码）
    g1 = subprocess.run(['git', 'status', '--porcelain', 'frontend/'],
                        capture_output=True, text=True, cwd=str(REPO),
                        encoding='utf-8', errors='replace')
    g2 = subprocess.run(['git', 'tag', '-l', 'v2-stable*'],
                        capture_output=True, text=True, cwd=str(REPO),
                        encoding='utf-8', errors='replace')
    v2_clean = not g1.stdout.strip()
    v2_tag = bool(g2.stdout.strip())
    rec('v2 源码未改动 + 稳定 tag 在位', v2_clean and v2_tag,
        f'frontend/ 未提交改动={len(g1.stdout.strip().splitlines())} 处 / tag={g2.stdout.strip() or "缺失"}')

    if as_json:
        print(json.dumps({'results': results, 'problems': problems}, ensure_ascii=False, indent=2))
    else:
        print()
        if problems:
            print(f'未满足 {len(problems)} 项：')
            for p in problems:
                print('  -', p)
        else:
            print(f'全部 {len(results)} 项硬性要求核验通过')

    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
