/**
 * 卡片整块可点 —— 真浏览器命中测试回归。
 *
 * 背景（真实事故）：知识笺卡片的整块点击原先靠一个绝对定位的 `.k-hit` 覆盖层实现，
 * 但它 z-index:0，而卡片里的子元素被给了 `position:relative; z-index:2`，
 * 于是覆盖层被盖住，**只有卡片边缘的缝隙能点到**。
 * 单元测试用 `trigger('click')` 直接派发事件、绕过命中测试，所以一直是绿的。
 * 这个用例用 `page.click()` 走真实命中测试（点的是卡片里的文字），能抓住这类回归。
 */
import { test, expect, mockApi, knowledgeRows, formulaRows } from './fixtures.js'

test.describe('卡片整块可点', () => {
  test('点知识笺正文（不是按钮）就打开详情弹窗', async ({ page }) => {
    await mockApi(page)
    await page.goto('/knowledge')

    const card = page.locator('.k-card', { hasText: knowledgeRows[0].tag_name })
    await expect(card).toBeVisible()
    // 点卡片中部的摘要文字 —— 事故时这一处正是"点不动"的位置
    await card.locator('.k-summary').click()

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('.modal-title')).toHaveText(knowledgeRows[0].tag_name)
    // 详情里应有全文，而不只是打开了一个空壳
    await expect(dialog).toContainText('用多项式逼近函数')
  })

  test('键盘 Enter / Space 也能打开详情（无障碍等价入口）', async ({ page }) => {
    await mockApi(page)
    await page.goto('/knowledge')

    const card = page.locator('.k-card', { hasText: knowledgeRows[1].tag_name })
    await card.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog').locator('.modal-title')).toHaveText('长难句拆分')

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()

    await card.focus()
    await page.keyboard.press('Space')
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('点卡片内的操作按钮不会顺带打开详情（@click.stop 生效）', async ({ page }) => {
    await mockApi(page)
    await page.goto('/knowledge')

    const card = page.locator('.k-card', { hasText: knowledgeRows[0].tag_name })
    await card.getByRole('button', { name: '编辑' }).click()

    // 应该打开"编辑"弹窗，而不是只读详情
    await expect(page.getByRole('dialog').locator('.modal-title')).not.toHaveText('泰勒公式')
    await expect(page.getByRole('dialog')).toBeVisible()
  })

  test('点公式卡正文打开公式详情', async ({ page }) => {
    await mockApi(page)
    await page.goto('/formulas')

    const card = page.locator('.formula-card', { hasText: formulaRows[0].title }).first()
    await expect(card).toBeVisible()
    // 点卡内的预览文字（非操作按钮）——命中测试必须落在卡片本身上
    await card.locator('.formula-preview').click()

    await expect(page.getByRole('dialog').locator('.modal-title')).toHaveText(formulaRows[0].title)
  })
})
