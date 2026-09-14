/**
 * pre-commit 前端钩子入口（跨平台，不依赖 bash —— Windows 上没有 bash）。
 *
 * 用法：node scripts/frontend_lint.mjs check|format
 *   check  → eslint + prettier --check（不修改文件，适合 CI/提交前拦截）
 *   format → eslint --fix + prettier --write
 */
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = join(here, '..', 'frontend')
const mode = process.argv[2] === 'format' ? 'format' : 'check'

// Windows 上 npx 是 .cmd，需要 shell
const run = (args) => {
  const res = spawnSync('npx', args, {
    cwd: frontend,
    stdio: 'inherit',
    shell: true,
  })
  return res.status ?? 1
}

// e2e 与 playwright.config.js 一并纳入检查：E2E 代码同样是工程资产，
// 且它跑在 Node 里（不是打包产物），lint 能提前抓出漏 import 之类的问题
const globs = [
  'src/**/*.{js,vue,css}',
  'tests/**/*.js',
  'e2e/**/*.js',
  'playwright.config.js',
]
const eslintTargets = ['src', 'tests', 'e2e', 'playwright.config.js']
const eslintArgs =
  mode === 'format' ? ['eslint', ...eslintTargets, '--fix'] : ['eslint', ...eslintTargets]
const prettierArgs =
  mode === 'format'
    ? ['prettier', '--write', ...globs]
    : ['prettier', '--check', ...globs]

const a = run(eslintArgs)
const b = run(prettierArgs)
process.exit(a === 0 && b === 0 ? 0 : 1)
