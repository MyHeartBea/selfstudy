"""校验 CI 工作流 YAML 的结构，并列出 job/step 概要。

用途：GitHub 对**语法非法的 workflow 会静默拒绝**（不报错、不运行），
症状是"推送后完全没有任何 run"。本项目遇到过这个怀疑点，所以留一个本地校验脚本。
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print('缺少 pyyaml，无法校验（pip install pyyaml）')
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / '.github' / 'workflows' / 'ci.yml'


def main() -> int:
    raw = WF.read_text(encoding='utf-8')
    try:
        doc = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f'YAML 解析失败（GitHub 会静默拒绝整个 workflow）：\n{exc}')
        return 1

    problems = []
    # YAML 会把裸 `on:` 解析成布尔键 True（这是合法 YAML 但容易误读），检查两种写法
    triggers = doc.get('on') or doc.get(True)
    if not triggers:
        problems.append('缺少 on: 触发器')
    jobs = doc.get('jobs') or {}
    if not jobs:
        problems.append('缺少 jobs')

    print(f'workflow 文件: {WF.relative_to(ROOT)}')
    print(f'触发器: {list(triggers.keys()) if isinstance(triggers, dict) else triggers}')
    print(f'job 数: {len(jobs)}')
    for name, job in jobs.items():
        steps = job.get('steps') or []
        wd = (job.get('defaults') or {}).get('run', {}).get('working-directory')
        print(f'  - {name}: runs-on={job.get("runs-on")} steps={len(steps)} wd={wd}')
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                problems.append(f'{name} 第 {i} 个 step 不是映射')
                continue
            if 'uses' not in step and 'run' not in step:
                problems.append(f'{name} 第 {i} 个 step 既没有 uses 也没有 run')
            if 'uses' in step and 'run' in step:
                problems.append(f'{name} 第 {i} 个 step 同时有 uses 与 run（非法）')
            # run 步骤必须有 name 或被忽略；这里只检查空的 run
            if 'run' in step and not str(step.get('run', '')).strip():
                problems.append(f'{name} 第 {i} 个 step 的 run 为空')

    if problems:
        print('\n发现问题：')
        for p in problems:
            print('  -', p)
        return 1
    print('\n结论: 结构合法')
    return 0


if __name__ == '__main__':
    sys.exit(main())
