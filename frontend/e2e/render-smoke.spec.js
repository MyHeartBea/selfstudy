/**
 * 渲染烟测：所有主路由在真浏览器里能渲染出内容（不只是 200 的 HTML 外壳）。
 *
 * 之所以有价值：`/stats` 这类接口即使返回错误，SPA 也会回 200 + 空壳 HTML，
 * 用 HTTP 状态码验证是**假阳性**（本项目踩过这个坑，健康检查因此改成 /api/health）。
 *
 * **强度说明**：断言的是各页写死的标题/关键词，所以它证明的是"组件挂上了、模板没崩、
 * 没有 JS 异常"，**不证明数据渲染正确**（数据链路由 capture / card-click 覆盖）。
 * 未打桩的接口由 expectAllApiStubbed 抓出来，避免"数据全挂但静态标题还在"的假绿。
 */
import { test, expect, mockApi, guardPageErrors, expectAllApiStubbed } from './fixtures.js'

const ROUTES = [
  { path: '/stats', marker: /今日|统计/ },
  { path: '/mistakes', marker: /错题/ },
  { path: '/capture', marker: /智能录入/ },
  { path: '/review', marker: /复习/ },
  { path: '/practice', marker: /练习/ },
  { path: '/vocab', marker: /生词/ },
  { path: '/knowledge', marker: /知识/ },
  { path: '/formulas', marker: /公式/ },
  { path: '/subjects', marker: /科目|指南/ },
  { path: '/papers', marker: /真题|卷/ },
  { path: '/essays', marker: /作文/ },
  // 只读巡检页（不在 Dock 里，直链/命令面板进入）：漏打桩会让它显示成"没查到"
  { path: '/integrity', marker: /数据体检/ },
  // 整库回滚页同上，且它一进来就要拉快照列表 —— 漏打桩会渲染成"还没有任何快照"
  { path: '/snapshots', marker: /数据备份与回滚/ },
]

for (const route of ROUTES) {
  test(`${route.path} 能在真浏览器里渲染`, async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto(route.path)

    await expect(page.locator('#app')).toBeVisible()
    await expect(page.locator('#app')).toContainText(route.marker)
    // 全局考研倒计时印：外壳层元素，每条路由都必须看得到（漏打桩 /exam-countdown 会让它消失）
    const cd = page.locator('.exam-cd').first()
    await expect(cd).toBeVisible()
    await expect(cd).toContainText('91')

    expectAllApiStubbed(calls)
    // 页面级 JS 异常（渲染崩溃）必须为零
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
}
