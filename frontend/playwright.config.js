/**
 * Playwright E2E 配置：跑在**真实 Chromium** 里，覆盖单元测试（happy-dom）抓不到的东西。
 *
 * 为什么需要它：本项目出过两类只有真浏览器才能暴露的问题 ——
 *   1) 卡片整块可点：`.k-hit` 覆盖层被 `z-index:2` 的子元素盖住，
 *      单元测试用 `trigger('click')` 直接派发事件，**永远绕开命中测试**，全绿但线上只有缝隙能点；
 *   2) 智能录入多图暂存：粘贴用真实 `paste` 事件 + DataTransfer，单元测试无法真实复现。
 *
 * 用系统 Chrome（channel: 'chrome'）而不是下载 Playwright 自带 Chromium：
 * 本机已有 Chrome，省一次几百 MB 下载；CI 上则装官方 chromium（见 ci.yml）。
 *
 * 后端不需要启动：所有 /api/** 请求都在用例里用 page.route 打桩（见 e2e/fixtures.js），
 * 所以 E2E 是**自洽**的，不依赖 8000 端口、不碰真实数据库。
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.E2E_PORT) || 5174
const BASE_URL = `http://127.0.0.1:${PORT}`
// CI 里装的是 Playwright 自带 chromium；本机用系统 Chrome（无需额外下载）
const useSystemChrome = !process.env.CI

export default defineConfig({
  testDir: './e2e',
  // 每个用例都在独立的浏览器上下文里跑，互不串味
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
    // strictPort 保证端口被占时直接失败，而不是静默换端口导致 baseURL 打空
    ...(useSystemChrome ? { channel: 'chrome' } : {}),
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // 手机档只跑渲染烟测：卡片点击与小屏命中区域都值得回归
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testMatch: /render-smoke\.spec\.js/ },
  ],
  webServer: {
    command: 'npm run dev -- --strictPort',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
