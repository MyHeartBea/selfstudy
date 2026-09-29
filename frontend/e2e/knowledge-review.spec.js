/**
 * 知识点复习(SM-2)——单测覆盖不到的浏览器链路:
 * 到期弹窗 → 先回忆门禁(未揭示判分按钮禁用) → 揭示摘要 → 判分 → 队列缩短 → 完成页。
 * 键盘流由单测覆盖;这里钉"按钮真的能按计划走完一轮"的浏览器链路。
 */
import { test, expect, mockApi, guardPageErrors } from './fixtures.js'

const queueRows = [
  {
    id: 201,
    tag_name: '泰勒公式',
    subject_name: '数学二',
    summary: '用多项式逼近函数,注意展开点与余项。',
    related_tags: ['导数'],
    review_count: 1,
    next_review_at: '2020-01-01 00:00:00',
  },
  {
    id: 202,
    tag_name: '中值定理',
    subject_name: '数学二',
    summary: '罗尔与拉格朗日中值定理的条件与结论。',
    related_tags: [],
    review_count: 1,
    next_review_at: '2020-01-01 00:00:00',
  },
]

test.describe('知识点复习', () => {
  test('先回忆门禁 → 揭示 → 判分 → 队列缩短 → 完成页', async ({ page }) => {
    const errors = guardPageErrors(page)
    await mockApi(page, {
      '/api/knowledge/review/queue': { items: queueRows, dueTotal: 2, returned: 2 },
      '/api/knowledge/201/review': { id: 201 },
      '/api/knowledge/202/review': { id: 202 },
    })
    await page.goto('/knowledge')

    await page.getByRole('button', { name: '复习知识点' }).click()
    await expect(page.locator('.kr-progress')).toContainText('到期 2')

    // 门禁:未揭示摘要前,忘了/记住了必须禁用(口径与闪卡翻面一致)
    await expect(page.getByRole('button', { name: '记住了' })).toBeDisabled()
    await expect(page.getByRole('button', { name: '忘了' })).toBeDisabled()

    // 揭示摘要后判分按钮可用,摘要内容真的渲染出来
    await page.getByRole('button', { name: '回忆一下，再显示摘要' }).click()
    await expect(page.locator('.kr-summary')).toContainText('用多项式逼近函数')
    await expect(page.getByRole('button', { name: '记住了' })).toBeEnabled()

    // 判分第一条 → 队列推进到第二条
    await page.getByRole('button', { name: '记住了' }).click()
    await expect(page.locator('.kr-name')).toContainText('中值定理')

    // 判分第二条 → 完成页
    await page.getByRole('button', { name: '回忆一下，再显示摘要' }).click()
    await page.getByRole('button', { name: '记住了' }).click()
    await expect(page.locator('.kr-done')).toContainText('本轮复习完成')

    expect(errors).toEqual([])
  })
})
