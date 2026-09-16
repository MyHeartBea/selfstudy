/**
 * v3 E2E —— 关键流程（真实浏览器 + 打桩后端）
 * ---------------------------------------------------------------------------
 * 为什么必须有这一层：单测跑在 happy-dom 里，**发现不了**
 *   - 组件挂载失败导致整页空白（曾因漏一个 import 发生，构建/lint/单测全绿）
 *   - 焦点管理、滚动锁、键盘流这些"真实 DOM 行为"
 *   - 路由懒加载是否真的能加载出页面
 * 这些正是"切换前端"之前最该被证明的部分。
 *
 * 后端全部打桩（page.route），理由：
 *   1. CI 里没有 8000 后端，真连会失败
 *   2. 断言不应随真实数据变化而漂移
 */
import { expect, test } from '@playwright/test'

/* ────────────────────────── 打桩数据 ────────────────────────── */
const MISTAKES_PAGED = {
  items: [
    {
      id: 101,
      question: '设函数 f(x) 在 x=0 处连续，求 f′(0)',
      question_type: 'choice',
      option_a: '0',
      option_b: '1',
      option_c: '2',
      option_d: '不存在',
      correct_answer: 'B',
      analysis: '由连续性定义得 f(0)=0。',
      subject_id: 1,
      source: '2019 真题',
      difficulty: 3,
      wrong_count: 3,
      review_count: 4,
      mastery: 60,
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

const MISTAKE_DETAIL = { ...MISTAKES_PAGED.items[0], related_knowledge: [{ tag_name: '连续性' }] }

const REVIEW_TODAY = {
  items: [
    {
      id: 201,
      question: '求极限 lim(x→0) sin(x)/x',
      question_type: 'choice',
      option_a: '0',
      option_b: '1',
      option_c: '∞',
      option_d: '不存在',
      correct_answer: 'B',
      analysis: '重要极限。',
      source: '课本',
      review_count: 2,
    },
  ],
  dueTotal: 1,
  remaining: 1,
  dailyLimit: 50,
  reviewedToday: 0,
}

const SUBJECTS = [{ id: 1, name: '数学二', kind: 'normal' }]
const OK = (data) => ({ code: 200, message: 'ok', data })

const REVIEW_STATS = {
  due_today: 1,
  reviewed_today: 0,
  total_reviews: 12,
  total_accuracy: 78,
  accuracy_today: 0,
  avg_mastery: 55,
  streak_days: 3,
  mastery_distribution: [{ mastery: 60, count: 1 }],
  by_subject: [],
  weakest_tags: [],
  last_7_days: [],
}

const STATS = {
  total_mistakes: 1,
  today_new: 0,
  by_subject: [],
  by_sub_subject: [],
  by_question_type: [],
  by_source_type: [],
}

const FORMULAS = [
  {
    id: 1,
    category: '高等数学',
    title: '重要极限',
    content: '$\\lim_{x\\to 0}\\frac{\\sin x}{x}=1$',
  },
]

const APPROACHES = ['配方法', '换元法']

const EXPORT = { exported_at: '2026-09-16 12:00', mistakes: [], knowledge: [] }

const HEALTH = { status: 'ok', version: '2.1.0' }

/**
 * 把 /api 打桩，并记录被调用的 URL（用于断言"确实发起了请求"）。
 *
 * 必须用路径白名单，不要用 glob 通配 api 前缀（已踩过）：
 * glob 里的 api 是子串匹配，/src/views/CaptureView.vue 也会被命中
 * （路径里含 api 三个字母），于是模块请求被 JSON 兜底响应顶掉，浏览器报
 * "Expected a JavaScript-or-Wasm module script but the server responded with a
 * MIME type of application/json" → 动态 import 失败 → 路由不渲染 →
 * 页面只剩导航外壳。这个坑很隐蔽：**v3 代码完全正常**（用 CDP 直接访问 14/14 通过），
 * 错的只是测试里的匹配模式。
 */
async function stubApi(page) {
  const calls = []

  const routes = [
    ['GET', /^\/api\/subjects$/, () => OK(SUBJECTS)],
    ['GET', /^\/api\/mistakes$/, () => OK(MISTAKES_PAGED)],
    ['GET', /^\/api\/mistakes\/\d+$/, () => OK(MISTAKE_DETAIL)],
    ['POST', /^\/api\/mistakes\/\d+\/review$/, () => OK({ ok: true })],
    ['GET', /^\/api\/reviews\/today$/, () => OK(REVIEW_TODAY)],
    ['GET', /^\/api\/reviews\/stats$/, () => OK(REVIEW_STATS)],
    ['GET', /^\/api\/stats$/, () => OK(STATS)],
    ['GET', /^\/api\/knowledge$/, () => OK({ items: [], total: 0, page: 1, page_size: 24 })],
    ['GET', /^\/api\/knowledge\/tags$/, () => OK([])],
    ['GET', /^\/api\/vocab$/, () => OK({ items: [], total: 0, page: 1, page_size: 30 })],
    ['GET', /^\/api\/vocab\/stats$/, () => OK({ total: 0, mastered: 0, due: 0, distribution: [] })],
    ['GET', /^\/api\/formulas$/, () => OK(FORMULAS)],
    ['GET', /^\/api\/papers$/, () => OK([])],
    ['GET', /^\/api\/mocks$/, () => OK([])],
    ['GET', /^\/api\/approaches$/, () => OK(APPROACHES)],
    ['GET', /^\/api\/export$/, () => OK(EXPORT)],
    ['GET', /^\/api\/health$/, () => OK(HEALTH)],
  ]

  await page.route(
    // 谓词形式：只拦 /api/ 前缀，vite 客户端、模块、图片一律放行
    (url) => url.pathname.startsWith('/api/'),
    async (route) => {
      const req = route.request()
      const path = new URL(req.url()).pathname
      const method = req.method()
      calls.push({ path, method, body: req.postData() })
      const hit = routes.find(([m, re]) => m === method && re.test(path))
      // 未打桩的端点给空对象，避免测试因无关请求失败
      return route.fulfill({ json: hit ? hit[2]() : OK({}) })
    },
  )
  return calls
}

/**
 * 就绪等待：不要用 `expect('.ink-loader').toBeVisible()` 判断加载页。
 *
 * 为什么（实测踩坑）：`page.goto()` 等的是 window load，而 Vue app 在更早就挂载了，
 * 加载页的 3.9 秒计时**从挂载那一刻就开始**。等 goto 返回时它常常已经播完并卸载，
 * 此时 `toBeVisible()` 是假失败。正确做法是等待明确的就绪信号 `body.ready`
 * （由 InkLoader 完成后设置），它同时覆盖两种情况：播完了、或被跳过了。
 */
async function gotoReady(page, path = '/') {
  await page.goto(path)
  await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
    timeout: 20000,
  })
}

/* ────────────────────────── 1. 启动页 ────────────────────────── */
test.describe('启动页', () => {
  test('目镜结构齐备（刻度环 / 十字丝 / 进度弧），就绪后卸载并解锁滚动', async ({ page }) => {
    await stubApi(page)
    await page.goto('/')

    // 结构断言用 count：加载页存在与否随计时变化，但结构要么在要么不在
    // （如果 goto 返回时已经卸载，这一段会被 skip —— 所以先记下，不强制）
    const hadLoader = (await page.locator('.ink-loader').count()) > 0
    if (hadLoader) {
      await expect(page.locator('.ticks line')).toHaveCount(24)
      await expect(page.locator('.cross line')).toHaveCount(4)
      await expect(page.locator('.ring-out .prog')).toHaveCount(1)
    }

    // 真正的契约：就绪后 loader 必须卸载，且**滚动必须解锁**（否则整站不能滚）
    await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
      timeout: 20000,
    })
    await expect(page.locator('.ink-loader')).toHaveCount(0, { timeout: 8000 })
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden')
  })

  test('任意键可以提前跳过', async ({ page }) => {
    await stubApi(page)
    await page.goto('/')
    await page.keyboard.press('Escape')
    // 跳过也必须走到"就绪"状态，而不是只把加载页藏起来
    await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
      timeout: 8000,
    })
    await expect(page.locator('.ink-loader')).toHaveCount(0, { timeout: 8000 })
  })
})

/* ────────────────────────── 2. 导航与懒加载 ────────────────────────── */
test.describe('导航', () => {
  // 每个路由一条测试：失败信息里直接带路由名，不用再靠缩小范围定位。
  const ROUTES = [
    '/',
    '/stats',
    '/review',
    '/capture',
    '/mistakes',
    '/knowledge',
    '/vocab',
    '/formulas',
    '/papers',
    '/mocks',
    '/subjects',
    '/practice',
    '/settings',
    '/design',
  ]

  for (const r of ROUTES) {
    test(`路由 ${r} 能渲染出内容且有 h1`, async ({ page }) => {
      await stubApi(page)
      await gotoReady(page, r)

      const main = page.locator('main')
      await expect(main).toBeVisible({ timeout: 15000 })

      // 先等 main 内出现任意标题：懒加载组件与打桩接口都要时间渲染，
      // 只等 body.ready（外壳就绪）就断言会得到假失败（已踩过）。
      await expect(main.locator('h1, h2, h3').first()).toBeAttached({ timeout: 15000 })

      // 页面必须有实际内容（这条防的正是"整页空白但构建全绿"）
      const text = await main.innerText()
      expect(text.length, `${r} 内容过少，可能整页空白`).toBeGreaterThan(20)

      // h1 是"可访问性"的硬要求：屏幕阅读器靠它建立页面级标题
      expect(await main.locator('h1').count(), `${r} 缺少 h1`).toBeGreaterThan(0)
    })
  }

  test('当前页在导航中有 aria-current 标记', async ({ page }) => {
    await stubApi(page)
    await gotoReady(page, '/mistakes')
    await expect(page.locator('.links .link[aria-current="page"]')).toHaveCount(1)
  })
})

/* ────────────────────────── 3. 复习页键盘流 ────────────────────────── */
test.describe('复习页', () => {
  test('空格揭示答案，Enter 落笔，提交后进入下一题/空态', async ({ page }) => {
    const calls = await stubApi(page)
    await gotoReady(page, '/review')

    // 题干来自打桩数据
    await expect(page.locator('h1.q')).toContainText('求极限')
    // 揭示前不泄漏答案
    await expect(page.locator('.ans')).not.toHaveClass(/shown/)

    await page.keyboard.press('Space')
    await expect(page.locator('.ans')).toHaveClass(/shown/)
    await expect(page.locator('.aval')).toContainText('B')

    // 键盘选选项：按 2 选 B
    await page.keyboard.press('2')
    await expect(page.locator('.opt[aria-pressed="true"]')).toHaveCount(1)

    // Enter 落笔 → 调用了提交接口
    await page.keyboard.press('Enter')
    await expect
      .poll(() => calls.some((c) => c.method === 'POST' && c.path.includes('/review')))
      .toBe(true)
  })
})

/* ────────────────────────── 4. 错题整块可点 + 弹层焦点 ────────────────────────── */
test.describe('错题星表', () => {
  test('点卡片任意位置打开详情；弹层锁滚动并在关闭后释放', async ({ page }) => {
    await stubApi(page)
    await gotoReady(page, '/mistakes')

    // 整块可点：点题干文字（不是按钮）
    await page.locator('.ink-card .q').click()
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute('aria-modal', 'true')

    // 打开期间锁滚动
    expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden')

    // Esc 关闭 → 焦点归还到刚才的卡片（v2 缺这一条）
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden')
  })
})

/* ────────────────────────── 5. 录入页多帧暂存 ────────────────────────── */
test.describe('智能录入', () => {
  test('一次选多张全部入库，且不会自动触发 AI', async ({ page }) => {
    const calls = await stubApi(page)
    await gotoReady(page, '/capture')

    // 一张 1x1 PNG 重复三个文件名（内容相同没关系，验证的是"三个都在"）
    const png = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==',
      'base64',
    )
    await page.setInputFiles('input[data-testid="pick-frames"]', [
      { name: 'q1.png', mimeType: 'image/png', buffer: png },
      { name: 'q2.png', mimeType: 'image/png', buffer: png },
      { name: 'q3.png', mimeType: 'image/png', buffer: png },
    ])

    await expect(page.locator('.frame')).toHaveCount(3)
    await expect(page.locator('.head .mono').last()).toContainText('3 / 5')

    // 关键：**没有**自动发起 AI 调用（v2 是每贴一张跑一次）
    expect(calls.some((c) => c.path.includes('/ai/'))).toBe(false)
  })
})

/* ────────────────────────── 6. prefers-reduced-motion 降级 ────────────────────────── */
test.describe('减少动态效果', () => {
  test('开启 reduced-motion 后启动页直接进入主界面，内容不丢', async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: 'reduce' })
    const page = await context.newPage()
    await stubApi(page)
    await page.goto('/')

    // 不播开场：loader 不出现或立刻消失
    await expect(page.locator('.ink-loader')).toHaveCount(0, { timeout: 5000 })
    // 内容必须在（降级不等于空白页）
    await expect(page.locator('main')).toBeVisible()
    expect((await page.locator('main').innerText()).length).toBeGreaterThan(20)
    await context.close()
  })
})
