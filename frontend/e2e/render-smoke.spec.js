/**
 * 渲染烟测：所有主路由在真浏览器里能渲染出内容（不只是 200 的 HTML 外壳）。
 *
 * 之所以有价值：`/stats` 这类接口即使返回错误，SPA 也会回 200 + 空壳 HTML，
 * 用 HTTP 状态码验证是**假阳性**（本项目踩过这个坑，健康检查因此改成 /api/health）。
 * 这里断言页面里真的出现了该页特有的文字。
 */
import { test, expect, mockApi } from './fixtures.js'

const ROUTES = [
  { path: '/stats', marker: /今日|统计/ },
  { path: '/mistakes', marker: /错题/ },
  { path: '/capture', marker: /智能录入/ },
  { path: '/review', marker: /复习/ },
  { path: '/vocab', marker: /生词/ },
  { path: '/knowledge', marker: /知识/ },
  { path: '/formulas', marker: /公式/ },
  { path: '/papers', marker: /真题|卷/ },
]

for (const route of ROUTES) {
  test(`${route.path} 能在真浏览器里渲染`, async ({ page }) => {
    const errors = []
    page.on('pageerror', (err) => errors.push(String(err)))
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })

    await mockApi(page)
    await page.goto(route.path)

    await expect(page.locator('#app')).toBeVisible()
    await expect(page.locator('#app')).toContainText(route.marker)
    // 页面级 JS 异常（渲染崩溃）必须为零
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
}
