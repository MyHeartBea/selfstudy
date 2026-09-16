/**
 * pre-commit 前端钩子入口（跨平台，不依赖 bash —— Windows 上没有 bash）。
 *
 * 用法：node scripts/frontend_lint.mjs check|format [--dir frontend|frontend-v3]
 *   check  → eslint + prettier --check（不修改文件，适合 CI/提交前拦截）
 *   format → eslint --fix + prettier --write
 *
 * 为什么带 --dir：v2（frontend/）与 v3（frontend-v3/）是两套独立的依赖与配置，
 * 各自在自己目录里跑自己的 eslint/prettier，避免把一个版本的规则套到另一个版本。
 */
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)
const mode = argv[0] === 'format' ? 'format' : 'check'
const dirIdx = argv.indexOf('--dir')
const dirName = dirIdx >= 0 && argv[dirIdx + 1] ? argv[dirIdx + 1] : 'frontend'
const frontend = join(here, '..', dirName)

if (!existsSync(frontend)) {
  console.log(`跳过：${dirName} 不存在`)
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

// 按存在性组装检查目标：e2e 只有 v2 有，v3 目前没有 tests 之外的扩展目录
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
  console.log(`跳过：${dirName} 里没有可检查的目标`)
  process.exit(0)
}

const eslintArgs = mode === 'format' ? ['eslint', ...targets, '--fix'] : ['eslint', ...targets]
const prettierArgs =
  mode === 'format' ? ['prettier', '--write', ...globs] : ['prettier', '--check', ...globs]

const a = run(eslintArgs)
const b = run(prettierArgs)
process.exit(a === 0 && b === 0 ? 0 : 1)
