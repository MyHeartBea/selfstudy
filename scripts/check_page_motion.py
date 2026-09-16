"""静态断言：用了 usePageMotion 的页面必须同时具备 import、根元素 ref、调用。

为什么需要这道检查（真实事故）：
    一次批量脚本给六个页面注入 usePageMotion 时，有两页只注入了**调用**、没注入 **import**，
    结果是运行时报 `usePageMotion is not defined` → **组件挂载失败 → 整页空白**，
    而且 `window.onerror` / 'error' 事件**不会触发**（只有 unhandledrejection 能看到），
    排查成本极高（页面白屏、控制台干净、构建与 lint 全部通过）。

    所以把"三者必须同时存在"变成一条可执行断言，放进 pre-commit 与 CI。

检查内容（frontend-v3/src/views/*.vue）：
  - 若文件里出现 `usePageMotion(` 调用，则必须同时存在
      (a) `import { usePageMotion } from '.../usePageMotion'`
      (b) 模板里有 ref="pageRoot"
      (c) 传给 usePageMotion 的正是 pageRoot
  - 若模板里有 data-reveal，则必须有 .reveal 类（否则加了 .in 也没有过渡效果）
  - 若模板里有 ref="pageRoot"，则必须有 usePageMotion 调用（否则白声明）

退出码：0 通过；1 有问题（并打印 file:line 证据）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWS = REPO_ROOT / 'frontend-v3' / 'src' / 'views'

CALL_RE = re.compile(r'usePageMotion\s*\(')
IMPORT_RE = re.compile(r"import\s*\{\s*usePageMotion\s*\}\s*from\s*'[^']*usePageMotion'")
REF_RE = re.compile(r'ref="pageRoot"')
PASS_RE = re.compile(r'usePageMotion\s*\(\s*pageRoot\b')
DATA_REVEAL_RE = re.compile(r'<[a-zA-Z][^>]*\bdata-reveal\b[^>]*>')
REVEAL_CLASS_RE = re.compile(r'class="[^"]*\breveal\b[^"]*"')


def line_of(text: str, index: int) -> int:
    return text.count('\n', 0, index) + 1


def main() -> int:
    if not VIEWS.is_dir():
        print(f'跳过：{VIEWS} 不存在')
        return 0

    problems: list[str] = []

    for path in sorted(VIEWS.glob('*.vue')):
        text = path.read_text(encoding='utf-8')
        rel = path.relative_to(REPO_ROOT)

        call = CALL_RE.search(text)
        has_import = bool(IMPORT_RE.search(text))
        has_ref = bool(REF_RE.search(text))
        passes_root = bool(PASS_RE.search(text))

        if call:
            if not has_import:
                problems.append(
                    f'{rel}:{line_of(text, call.start())}: 调用了 usePageMotion 但没有 import'
                    f' —— 运行时会整页空白（window error 事件不触发，极难排查）'
                )
            if not has_ref:
                problems.append(
                    f'{rel}:{line_of(text, call.start())}: 调用了 usePageMotion 但模板里没有 ref="pageRoot"'
                )
            if not passes_root:
                problems.append(
                    f'{rel}:{line_of(text, call.start())}: usePageMotion 的第一个参数不是 pageRoot'
                )

        if has_ref and not call:
            problems.append(
                f'{rel}: 模板声明了 ref="pageRoot" 但没有调用 usePageMotion（白声明，动效不会生效）'
            )

        # data-reveal 必须配 .reveal 类：usePageMotion 只加 .in，
        # 位移/透明度过渡定义在 materials.css 的 .reveal / .reveal.in 上
        for m in DATA_REVEAL_RE.finditer(text):
            tag = m.group(0)
            if 'class="' in tag and not REVEAL_CLASS_RE.search(tag):
                problems.append(
                    f'{rel}:{line_of(text, m.start())}: data-reveal 缺少 .reveal 类'
                    f'（只会加 .in，不会产生任何过渡效果）'
                )

    if problems:
        print('页面动效接线检查未通过：')
        for p in problems:
            print('  -', p)
        return 1

    print(f'页面动效接线检查通过（{len(list(VIEWS.glob("*.vue")))} 个视图）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
