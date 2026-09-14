/**
 * Playwright E2E 配置：跑在**真实 Chromium** 里，覆盖单元测试（happy-dom）抓不到的东西。
 *
 * 为什么需要它：本项目出过两类只有真浏览器才能暴露的问题 ——
 *   1) 卡片整块可点：`.k-hit` 覆盖层被 `z-index:2` 的子元素盖住，
 *      单元测试用 `trigger('click')` 直接派发事件，**永远绕开命中测试**，全绿但线上只有缝隙能点；
 *   2) 智能录入多图暂存：粘贴用真实 `paste` 事件 + DataTransfer，单元测试无法真实复现。
 *
 * 浏览器：CI 装 Playwright 自带 chromium；本机默认用系统 Chrome（省几百 MB 下载），
 * 没装 Chrome 时用 `E2E_CHROME=0 npx playwright install chromium` 装自带浏览器即可。
 *
 * 端口：默认 5274（**刻意与开发端口 5174 错开**）。若沿用 5174，本机已有一个旧
 * checkout 的 dev server 时，reuseExistingServer 会静默复用它 —— E2E 就在测旧代码。
 *
 * 后端不需要启动：所有 /api/** 请求都在用例里用 page.route 打桩（见 e2e/fixtures.js），
 * 所以 E2E 是**自洽**的，不依赖 8000 端口、不碰真实数据库。
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.E2E_PORT) || 5274
const BASE_URL = `http://127.0.0.1:${PORT}`
// 本机默认走系统 Chrome；显式 E2E_CHROME=0 可切回 Playwright 自带浏览器
const useSystemChrome = !process.env.CI && process.env.E2E_CHROME !== '0'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  timeout: 30_000,
  expect: { timeout: 7_000 },
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(useSystemChrome ? { channel: 'chrome' } : {}),
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // 手机档不只跑烟测：窄屏（≤1100px）会切成另一套布局（Dock 隐藏、抽屉生效），
    // "卡片整块可点"的命中测试在小屏同样值得回归。
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'] },
      testMatch: /(render-smoke|card-click)\.spec\.js/,
    },
  ],
  webServer: {
    command: `npm run dev -- --strictPort --port ${PORT}`,
    url: BASE_URL,
    // 端口被占就用现成的（本地开发惬意，但默认端口已与开发端口错开，避免误测旧代码）
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
