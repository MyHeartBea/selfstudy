/**
 * pre-commit 前端钩子入口（跨平台，不依赖 bash —— Windows 上没有 bash）。
 *
 * 用法：node scripts/frontend_lint.mjs check|format
 *   check  → eslint + prettier --check（不修改文件，适合 CI/提交前拦截）
 *   format → eslint --fix + prettier --write
 */
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const mode = process.argv[2] === 'format' ? 'format' : 'check'
const frontend = join(here, '..', 'frontend')

if (!existsSync(frontend)) {
  console.log('跳过：frontend 不存在')
  process.exit(0)
}

// Windows 上 npx 是 .cmd，需要 shell
const run = (args) => {
  const res = spawnSync('npx', args, {
    cwd: frontend,
    stdio: 'inherit',
    shell: true,
  })
  return res.status ?? 1
}

// 按存在性组装检查目标
const targets = []
for (const extra of ['src', 'tests', 'e2e', 'playwright.config.js', 'vite.config.js']) {
  if (existsSync(join(frontend, extra))) targets.push(extra)
}
const globs = []
for (const g of [
  'src/**/*.{js,vue,css}',
  'tests/**/*.js',
  'e2e/**/*.js',
  'playwright.config.js',
  'vite.config.js',
]) {
  const base = g.split('/')[0].replace('**', '').replace('*', '')
  if (existsSync(join(frontend, base))) globs.push(g)
}

if (!targets.length) {
  console.log('跳过：frontend 里没有可检查的目标')
  process.exit(0)
}

const eslintArgs = mode === 'format' ? ['eslint', ...targets, '--fix'] : ['eslint', ...targets]
const prettierArgs =
  mode === 'format' ? ['prettier', '--write', ...globs] : ['prettier', '--check', ...globs]

const a = run(eslintArgs)
const b = run(prettierArgs)
process.exit(a === 0 && b === 0 ? 0 : 1)
