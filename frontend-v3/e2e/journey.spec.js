/**
 * v3 用户旅程 E2E —— 防"能路由但点不动"这一类问题
 * ---------------------------------------------------------------------------
 * 为什么单独一个文件：
 *   之前 21 条 E2E 全部通过，却漏掉了"导航点不动"这个真 bug。
 *   根因是我用 `page.goto()` 直接跳路由，**从没在界面上真点过导航**；
 *   而 z-index 冲突只在"真实点击"时才暴露（elementFromPoint 命中的是内容层）。
 *   所以这组用例的原则是：**一切通过真实点击进入，并用元素命中验证可点性**。
 *
 * 三类断言：
 *   1. 命中（hit-testing）：目标中心点上的顶层元素必须是它自己或它的子元素
 *      —— 直接抓出"被覆盖层挡住"的问题
 *   2. 点击后到达预期路由
 *   3. 到达后有实际内容（防整页空白）
 */
import { expect, test } from '@playwright/test'

const NAV = [
  { href: '/stats', label: '成册' },
  { href: '/review', label: '复习' },
  { href: '/capture', label: '录入' },
  { href: '/mistakes', label: '错题' },
  { href: '/knowledge', label: '知识' },
  { href: '/vocab', label: '生词' },
  { href: '/formulas', label: '公式' },
  { href: '/papers', label: '真题' },
  { href: '/mocks', label: '模考' },
  { href: '/subjects', label: '科目' },
  { href: '/practice', label: '练习' },
  { href: '/settings', label: '设置' },
  { href: '/design', label: '规格' },
]

/** 打桩：只拦 /api/ 前缀（谓词形式，避免误伤 /src/views/*.vue 里的 "api" 子串） */
async function stub(page) {
  const ok = (data) => ({ code: 200, message: 'ok', data })
  const empty = { items: [], total: 0, page: 1, page_size: 20 }
  await page.route(
    (url) => url.pathname.startsWith('/api/'),
    (route) => {
      const p = new URL(route.request().url()).pathname
      if (p === '/api/subjects') return route.fulfill({ json: ok([{ id: 1, name: '数学二' }]) })
      if (p === '/api/reviews/stats')
        return route.fulfill({
          json: ok({
            due_today: 3,
            reviewed_today: 1,
            total_reviews: 42,
            total_accuracy: 70,
            accuracy_today: 50,
            avg_mastery: 40,
            streak_days: 5,
            mastery_distribution: [{ mastery: 40, count: 3 }],
            by_subject: [],
            weakest_tags: [],
            last_7_days: [],
          }),
        })
      if (p === '/api/stats')
        return route.fulfill({ json: ok({ total_mistakes: 105, today_new: 1, by_subject: [] }) })
      if (p === '/api/reviews/today')
        return route.fulfill({
          json: ok({
            items: [
              {
                id: 1,
                question: '求极限 lim sin(x)/x',
                question_type: 'choice',
                correct_answer: 'B',
              },
            ],
            dueTotal: 1,
            remaining: 1,
            dailyLimit: 50,
            reviewedToday: 0,
          }),
        })
      if (p === '/api/approaches') return route.fulfill({ json: ok(['配方法']) })
      if (p === '/api/formulas') return route.fulfill({ json: ok([]) })
      return route.fulfill({ json: ok(empty) })
    },
  )
}

async function gotoHome(page) {
  await page.goto('/')
  await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
    timeout: 20000,
  })
}

/**
 * 命中测试：返回目标中心点上的顶层元素是否属于该目标。
 * 这是本次新增的关键断言 —— 它直接等价于"用户点下去能不能命中"。
 */
async function hitTest(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel)
    if (!el) return { found: false }
    const r = el.getBoundingClientRect()
    if (r.width === 0 || r.height === 0) return { found: true, visible: false }
    const cx = r.x + r.width / 2
    const cy = r.y + r.height / 2
    const top = document.elementFromPoint(cx, cy)
    return {
      found: true,
      visible: true,
      hit: !!top && (top === el || el.contains(top) || top.contains(el)),
      topTag: top ? top.tagName.toLowerCase() : null,
      topClass: top && typeof top.className === 'string' ? top.className.split(' ')[0] : null,
    }
  }, selector)
}

test.describe('用户旅程：导航', () => {
  // 13 个导航项 × （约 4s 启动页 + 页面渲染）→ 需要比默认 45s 更宽的超时
  test('首页导航每一项都能命中且点击后到达对应页面', async ({ page }) => {
    test.setTimeout(180000)
    await stub(page)
    await gotoHome(page)

    for (const item of NAV) {
      const sel = `.links .link[href="${item.href}"]`
      // 1) 命中测试：目标不能被内容层盖住
      const hit = await hitTest(page, sel)
      expect(hit.found, `${item.label} 导航项不存在`).toBe(true)
      expect(
        hit.hit,
        `${item.label}（${item.href}）中心点被 ${hit.topTag}.${hit.topClass} 挡住，用户点不到`,
      ).toBe(true)

      // 2) 真实点击（不是 goto）
      await page.click(sel)
      await page.waitForURL(`**${item.href}`, { timeout: 10000 })

      // 3) 到达后有实际内容
      const main = page.locator('main')
      await expect(main).toBeVisible({ timeout: 10000 })
      await expect(main.locator('h1, h2, h3').first()).toBeAttached({ timeout: 12000 })
      expect((await main.innerText()).length, `${item.href} 内容过少`).toBeGreaterThan(20)

      // 回到首页继续下一项
      await gotoHome(page)
    }
  })

  test('首页正在展示的那一项带 aria-current，且可点', async ({ page }) => {
    await stub(page)
    await page.goto('/stats')
    await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
      timeout: 20000,
    })
    const cur = page.locator('.links .link[aria-current="page"]')
    await expect(cur).toHaveCount(1)
    await expect(cur).toHaveText(/成册/)
  })
})

test.describe('用户旅程：首页交互', () => {
  test('启动页期间首页保持隐藏，就绪后错峰到位', async ({ page }) => {
    await stub(page)
    await page.goto('/')

    // 先等加载页真正挂载（它可能在 goto 返回后才渲染）：
    // 若它在 1.5s 内出现，则此刻首页入场元素必须仍然隐藏 —— 这正是用户反馈
    // "进入动态和首页一起出现"要防的情况。若加载页已结束，说明本机太快，跳过该断言。
    const appeared = await page
      .locator('.ink-loader')
      .waitFor({ state: 'attached', timeout: 1500 })
      .then(() => true)
      .catch(() => false)

    if (appeared) {
      // 关键：1.3s 左右首页元素**还没挂载**（实测 0/0），此时取样会误判。
      // 先等入场元素真正挂载，再断言"启动页期间它们必须仍然隐藏"。
      await page
        .locator('.title .ln')
        .first()
        .waitFor({ state: 'attached', timeout: 4000 })
        .catch(() => {})
      const state = await page.evaluate(() => {
        const els = Array.from(document.querySelectorAll('.title .ln, .eyebrow, .foot'))
        const hidden = els.filter((e) => Number(getComputedStyle(e).opacity) < 0.15).length
        return {
          total: els.length,
          hidden,
          bodyReady: document.body.classList.contains('ready'),
          loaderThere: !!document.querySelector('.ink-loader'),
        }
      })
      // 只在"加载页仍在 且 body 尚未 ready"的窗口内做断言；
      // 若本机太快已经就绪，则本断言无意义（跳过），由后面的"就绪后全部到位"覆盖。
      if (state.total > 0 && state.loaderThere && !state.bodyReady) {
        expect(
          state.hidden,
          `启动页还在时首页已亮起 ${state.total - state.hidden}/${state.total} 个入场元素（两者同时出现）`,
        ).toBe(state.total)
      }
    }

    await page.waitForFunction(() => document.body.classList.contains('ready'), null, {
      timeout: 20000,
    })
    await expect(page.locator('.ink-loader')).toHaveCount(0, { timeout: 8000 })
    // 就绪后所有入场元素都应到位（错峰最晚 0.85s 起步 + 1.1s 过渡）
    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const els = document.querySelectorAll('.title .ln, .eyebrow, .foot')
            return Array.from(els).filter((e) => Number(getComputedStyle(e).opacity) < 0.15).length
          }),
        { timeout: 8000 },
      )
      .toBe(0)
  })

  test('滚动时宣言逐词点亮', async ({ page }) => {
    await stub(page)
    await gotoHome(page)

    const before = await page.locator('.w.on').count()

    // 先让宣言进入视口，再往下多滚一点把映射推到中段。
    // 不要用 offsetTop 手算（首屏 100svh + 懒加载内容会让它偏）。
    const mf = page.locator('.manifesto')
    await mf.scrollIntoViewIfNeeded()
    await page.evaluate(() => {
      document.documentElement.style.scrollBehavior = 'auto'
      window.scrollBy(0, Math.round(window.innerHeight * 0.35))
    })

    // 点亮是随滚动逐块推进的，给一点时间并轮询断言
    await expect
      .poll(() => page.locator('.w.on').count(), { timeout: 6000 })
      .toBeGreaterThan(before)
  })

  test('观测量每行整行可点并进入复习页', async ({ page }) => {
    await stub(page)
    await gotoHome(page)

    const rows = page.locator('.list .row')
    const n = await rows.count()
    expect(n).toBeGreaterThan(0)

    // 用原生 click：它自带可操作性检查（滚动进视口、等稳定、检查遮挡），
    // 点不动时会明确报"被哪个元素拦截点击"，比自算坐标可靠得多。
    await rows.first().click()
    await page.waitForURL('**/review', { timeout: 10000 })
  })

  test('收束区三个按钮都能点', async ({ page }) => {
    await stub(page)
    for (const [idx, path] of [
      [0, '/review'],
      [1, '/stats'],
      [2, '/capture'],
    ]) {
      await gotoHome(page)
      const btn = page.locator('.close .cl-acts button').nth(idx)
      await btn.scrollIntoViewIfNeeded()
      const hit = await page.evaluate((i) => {
        const b = document.querySelectorAll('.close .cl-acts button')[i]
        const r = b.getBoundingClientRect()
        const top = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
        return !!top && (top === b || b.contains(top))
      }, idx)
      expect(hit, `收束第 ${idx + 1} 个按钮被挡住`).toBe(true)
      await btn.click()
      await page.waitForURL(`**${path}`, { timeout: 10000 })
    }
  })
})
