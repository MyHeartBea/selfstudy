/**
 * Playwright 配置（v3 专用）
 * ---------------------------------------------------------------------------
 * 与 v2 的 e2e 完全独立：自己的端口、自己的 webServer、自己的测试目录。
 *
 * 端口用 5176（v2 的 e2e 用 5274，v3 dev 用 5175）：
 * 避免与正在运行的 dev server 抢端口 —— strictPort 会让抢占直接失败。
 *
 * 后端：**不依赖真实后端**。所有 /api 请求在各测试里用 page.route 打桩，
 * 这样 E2E 才能进 CI（CI 里没有 8000 后端）；同时也让断言不随数据变化而漂移。
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.V3_E2E_PORT) || 5176
const BASE = `http://127.0.0.1:${PORT}`

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  expect: { timeout: 8000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',

  use: {
    baseURL: BASE,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    // 无头环境需要的 GPU 开关：星点场用 WebGL，没有它着色器会直接失败
    launchOptions: {
      args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
    },
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        /* 本机已装 Chrome，优先复用它：Playwright 自带的 chromium 需要额外下载
           （本机网络下会超时）。CI 上是干净的 ubuntu 镜像，没有系统 Chrome，
           所以要回落到 Playwright 自带浏览器 —— 用环境变量区分：
             PW_USE_SYSTEM_CHROME=1  本地用系统 Chrome
           不设置时用 Playwright 自带（CI 行为）。 */
        ...(process.env.PW_USE_SYSTEM_CHROME ? { channel: 'chrome' } : {}),
      },
    },
  ],

  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: BASE,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})
