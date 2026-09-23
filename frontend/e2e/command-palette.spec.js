/**
 * 命令面板（Ctrl+K）全站搜索 —— 只有真浏览器能验的回归。
 *
 * 单测已经钉住 store 的摊平/分段/竞态；这里补的是它够不到的三段链路：
 *  1) **真命中**：`.palette-item` 是 Teleport 到 body 的，且键盘导航要求 ↑↓ 与鼠标高亮
 *     落在同一行 —— 分段渲染一旦把下标算成"组内序号"，只有真按一次方向键才看得见；
 *  2) **跳转参数真的被目标页吃掉**：`?search=` 必须在公式页真的过滤掉另一条，
 *     否则"搜到了却落在全量列表上"（这正是本批要修的缺陷）照样绿；
 *  3) Tab 换范围**不该**再打一次接口（结果已在本地，重发是旧实现的浪费）。
 */
import {
  test,
  expect,
  mockApi,
  guardPageErrors,
  expectAllApiStubbed,
  formulaRows,
} from './fixtures.js'

/** 两条公式，只有一条含"中值"：用来证明 ?search= 真的过滤了。 */
const FORMULAS = [
  {
    id: 202,
    category: '高等数学',
    title: '拉格朗日中值定理',
    content: "$f(b)-f(a)=f'(\\xi)(b-a)$",
    created_at: '2026-09-01 09:00:00',
  },
  ...formulaRows,
]

test.describe('命令面板全站搜索', () => {
  test('搜中值 → 三段分组渲染 → 方向键落到公式行 → 回车跳回并按关键词过滤', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, { '/api/formulas': FORMULAS })
    await page.goto('/stats')
    await expect(page.locator('body')).toHaveClass(/ready/)
    // body.ready 由 BootCalibration 独立加上，而 AppLayout 是懒加载的路由 chunk ——
    // 并发跑时 ready 可能先于外壳挂载出现，此刻 Ctrl+K 会落到还没挂监听的页面上被
    // 整个丢掉（面板的 keydown 监听挂在 CommandPalette 的 onMounted）。
    // .dock 可见 = AppLayout 已挂载 = 监听一定在了。
    await expect(page.locator('.dock')).toBeVisible()

    await page.keyboard.press('Control+k')
    await expect(page.locator('.palette-input')).toBeFocused()

    await page.locator('.palette-input').fill('中值')
    // 分段标题：三组各自的标签都要出现（顺序即后端 GROUPS 顺序）
    await expect(page.locator('.palette-list .palette-group')).toHaveText([
      /\d+ 条结果|搜索中/,
      '错题',
      '知识点',
      '公式',
    ])
    await expect(page.locator('.palette-item-label', { hasText: '拉格朗日中值定理' })).toBeVisible()
    // 过滤器上的命中数取后端每组的 total，不是"展示了几条"
    await expect(
      page.locator('.scope-chip', { hasText: '错题' }).locator('.scope-count'),
    ).toHaveText('3')

    const searchCalls = calls.filter((c) => c.path === '/api/search')
    expect(searchCalls, '没有打全站搜索接口').toHaveLength(1)
    expect(decodeURIComponent(searchCalls[0].url)).toContain('q=中值')

    // 摊平后是 错题1 / 知识点1 / 公式1：按两次 ↓ 才到公式行（下标必须是一维的）
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('ArrowDown')
    await expect(page.locator('.palette-item.active')).toContainText('拉格朗日中值定理')
    await page.keyboard.press('Enter')

    await page.waitForURL(/\/formulas\?search=/)
    await expect(page.locator('.count-tip')).toHaveText('共 1 条')
    await expect(page.getByText('拉格朗日中值定理').first()).toBeVisible()
    await expect(page.getByText('牛顿-莱布尼茨公式')).toHaveCount(0)
    // 跳转后面板必须收掉（路由变化触发 closePalette）
    await expect(page.locator('.palette-input')).toHaveCount(0)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('Tab 换范围只是本地过滤，不重新打接口', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/stats')
    await expect(page.locator('body')).toHaveClass(/ready/)
    // 同上：ready 先于懒加载外壳出现时，Ctrl+K 会被整个丢掉
    await expect(page.locator('.dock')).toBeVisible()

    await page.keyboard.press('Control+k')
    await expect(page.locator('.palette-input')).toBeFocused()
    await page.locator('.palette-input').fill('中值')
    await expect(page.locator('.palette-item')).toHaveCount(3)
    await expect(page.locator('.scope-chip.active')).toContainText('全部')

    await page.keyboard.press('Tab')
    await expect(page.locator('.scope-chip.active')).toContainText('错题')
    await expect(page.locator('.palette-item')).toHaveCount(1)
    await expect(page.locator('.palette-list .palette-group')).toHaveText(['1 条结果', '错题'])
    expect(calls.filter((c) => c.path === '/api/search')).toHaveLength(1)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
