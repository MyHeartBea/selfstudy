/**
 * 键盘与"离开保护"两条链路 —— 只有真浏览器能验的回归。
 *
 * 为什么放在 E2E 而不是单测：
 * 1. 星级键盘（U1）改的是 **Tab 可达性**。单测里 `trigger('keydown')` 是直接在元素上派发事件，
 *    等于跳过了"这个元素根本进不了 Tab 序列"这个真正的缺陷 —— 改之前整组是 role="img" 的裸 span，
 *    没有 tabindex，只用键盘的人在录入页的**必填项**「难度」上无处可去。
 * 2. 模考离开保护（U6）是 vue-router 的组件内守卫 + 全局确认弹窗，单测要仿真整条路由栈，
 *    不如真点一次链接来得可信（模考作答只暂存在内存，误点导航 = 整场作废且原先毫无提示）。
 */
import { test, expect, mockApi, guardPageErrors, expectAllApiStubbed } from './fixtures.js'

const mockQueue = {
  items: [
    {
      id: 901,
      question_type: 'choice',
      question: '设 $f(x)=x^2$，则 $f(1)$ 等于',
      option_a: '0',
      option_b: '1',
      option_c: '2',
      option_d: '3',
      correct_answer: 'B',
      analysis: '代入即可',
      images: [],
      knowledge_tags: [],
      difficulty: 2,
    },
    {
      id: 902,
      question_type: 'choice',
      question: '可导必连续，连续（　）可导',
      option_a: '一定',
      option_b: '不一定',
      option_c: '一定不',
      option_d: '与极限无关',
      correct_answer: 'B',
      analysis: '经典反例 $|x|$ 在 0 处连续但不可导',
      images: [],
      knowledge_tags: [],
      difficulty: 3,
    },
  ],
}

test.describe('难度星级键盘可达', () => {
  test('Tab 从上一个控件直接落进星级，方向键改分且焦点跟随', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/design')
    // 开场编排（启动遮罩 + BootCalibration）会占住焦点序列，等它放完再按 Tab
    await expect(page.locator('body')).toHaveClass(/ready/)

    const group = page.locator('.stars[role="radiogroup"]').first()
    await expect(group).toBeVisible()
    const radios = group.locator('[role="radio"]')
    // 组内只有一个 Tab 落点（roving tabindex），其余是 -1
    await expect(radios.nth(0)).toHaveAttribute('tabindex', '-1')

    // 关键断言：**从星级前面的那个复选框按一次 Tab，落点就是星级**。
    // 改之前星级是无 tabindex 的裸 span，Tab 会直接跳过它 —— 这一步当时必然红。
    await group.locator('xpath=preceding-sibling::label[1]//input').focus()
    await page.keyboard.press('Tab')
    const focused = group.locator('[role="radio"]:focus')
    await expect(focused, 'Tab 越过了星级（键盘用户仍够不到必填的「难度」）').toHaveCount(1)
    await expect(focused).toHaveAttribute('aria-label', '3 星')

    await expect(radios.nth(2)).toHaveAttribute('aria-checked', 'true')
    await page.keyboard.press('ArrowRight')
    await expect(radios.nth(3)).toHaveAttribute('aria-checked', 'true')
    await expect(radios.nth(2)).toHaveAttribute('aria-checked', 'false')
    // 焦点必须跟着走：否则"按了键但光标还在原地"，连按会跳着改分
    await expect(radios.nth(3)).toBeFocused()

    await page.keyboard.press('End')
    await expect(radios.nth(4)).toHaveAttribute('aria-checked', 'true')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})

test.describe('模考中途离开保护', () => {
  test('未作答可直接离开；作答后换页先确认，取消则留在原地', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, { '/api/reviews/practice': mockQueue })
    await page.goto('/review?mode=mock&duration=60')

    const timer = page.locator('.mock-timer')
    await expect(timer).toBeVisible()
    await expect(page.locator('.question-block').first()).toContainText('等于')
    await expect(page.getByRole('button', { name: /交卷（0\/2 已答）/ })).toBeVisible()

    // 一题未答：没有东西可丢，不该拦人
    await page.getByRole('button', { name: '重新选题' }).click()
    await page.waitForURL('**/practice')
    await page.goto('/review?mode=mock&duration=60')
    await expect(timer).toBeVisible()

    // 作答一题（第 1 题选 B）后换页 → 弹确认，且报出已答题数
    await page.locator('.option-row').nth(1).click()
    await expect(page.getByRole('button', { name: /交卷（1\/2 已答）/ })).toBeVisible()
    await page.getByRole('button', { name: '重新选题' }).click()

    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('已作答 1 题')
    await expect(page.locator('.mock-timer')).toBeVisible()

    // 取消：留在模考页，作答还在
    await dialog.getByRole('button', { name: '取消' }).click()
    await expect(dialog).toBeHidden()
    await expect(page).toHaveURL(/mode=mock/)
    await expect(page.getByRole('button', { name: /交卷（1\/2 已答）/ })).toBeVisible()

    // 确认离开：放行
    await page.getByRole('button', { name: '重新选题' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: '仍要离开' }).click()
    await page.waitForURL('**/practice')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
