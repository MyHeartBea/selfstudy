/**
 * 卡片整块可点 —— 真浏览器命中测试回归。
 *
 * 背景（真实事故）：知识笺卡片的整块点击原先靠一个绝对定位的 `.k-hit` 覆盖层实现，
 * 但它 z-index:0，而卡片里的子元素被给了 `position:relative; z-index:2`，
 * 于是覆盖层被盖住，**只有卡片边缘的缝隙能点到**。
 * 单元测试用 `trigger('click')` 直接派发事件、绕过命中测试，所以一直是绿的。
 * 这个用例用 `page.click()` 走真实命中测试（点的是卡片里的文字），能抓住这类回归。
 */
import {
  test,
  expect,
  mockApi,
  knowledgeRows,
  formulaRows,
  essayRows,
  essayResult,
  guardPageErrors,
  expectAllApiStubbed,
} from './fixtures.js'

test.describe('卡片整块可点', () => {
  test('点知识笺正文（不是按钮）就打开详情弹窗', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
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

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('键盘 Enter / Space 也能打开详情（无障碍等价入口）', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/knowledge')

    const card = page.locator('.k-card', { hasText: knowledgeRows[1].tag_name })
    const title = page.getByRole('dialog').locator('.modal-title')

    await card.focus()
    await page.keyboard.press('Enter')
    await expect(title).toHaveText('长难句拆分')

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()

    // Space 分支同样要校验标题：只断言"弹窗可见"的话，任何弹窗都能让它通过
    await card.focus()
    await page.keyboard.press('Space')
    await expect(title).toHaveText('长难句拆分')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('点卡片内的操作按钮不会顺带打开详情（@click.stop 生效）', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/knowledge')

    const card = page.locator('.k-card', { hasText: knowledgeRows[0].tag_name })
    await card.getByRole('button', { name: '编辑' }).click()

    // 正向断言：打开的是"编辑"弹窗（KnowledgeEditModal），不是只读详情。
    // 不能用 `.not.toHaveText(...)` —— Playwright 的否定断言在**元素不存在**时判定为通过，
    // 一旦标题类名改了就会静默变成"什么都没验"。
    const dialog = page.getByRole('dialog')
    await expect(dialog.locator('.modal-title')).toHaveText('编辑知识点摘要')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('点公式卡正文打开公式详情', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/formulas')

    const card = page.locator('.formula-card', { hasText: formulaRows[0].title }).first()
    await expect(card).toBeVisible()
    // 点卡内的预览文字（非操作按钮）——命中测试必须落在卡片本身上
    await card.locator('.formula-preview').click()

    await expect(page.getByRole('dialog').locator('.modal-title')).toHaveText(formulaRows[0].title)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('点作文卡正文打开批改详情（逐词改错要真渲染）', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/essays')

    const card = page.locator('.ea-card', { hasText: essayRows[0].excerpt })
    await expect(card).toBeVisible()
    await card.locator('.ea-excerpt').click()

    const dialog = page.getByRole('dialog')
    // 正向断言标题：详情弹窗与确认弹窗都可能是"某个弹窗"，只断言可见验不出打开了哪个
    await expect(dialog.locator('.modal-title')).toHaveText('作文批改详情')
    await expect(dialog.locator('.er-score')).toHaveText(String(essayResult.score))
    // 改错结果必须真的落到 DOM：LCS 逐词拆片，只有 go→goes 这一处变动
    await expect(dialog.locator('.er-corr-item .d-del')).toHaveText('go')
    await expect(dialog.locator('.er-corr-item .d-ins')).toHaveText('goes')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('点删除按钮只弹确认框，确认后卡片消失（@click.stop 生效）', async ({ page }) => {
    const errors = guardPageErrors(page)
    let deleted = false
    const calls = await mockApi(page, {
      '/api/essays': () =>
        deleted ? { items: [], total: 0 } : { items: essayRows, total: essayRows.length },
      '/api/essays/301': ({ method }) => {
        if (method === 'DELETE') deleted = true
        return { ...essayRows[0], essay_text: essayResult.raw_transcript, result: essayResult }
      },
    })
    await page.goto('/essays')

    const card = page.locator('.ea-card', { hasText: essayRows[0].excerpt })
    await card.locator('.ea-del').click()

    // 打开的是确认框（标题即"详情没开"的正向证明），不是作文详情弹窗
    const confirm = page.getByRole('dialog')
    await expect(confirm.locator('.modal-title')).toHaveText('删除这条作文记录？')
    await expect(confirm.locator('.confirm-msg')).toContainText('不可恢复')

    await confirm.getByRole('button', { name: '确定' }).click()
    // 断言"结果已渲染"而不是请求发过：删除后列表换成空态
    await expect(page.getByText('还没有批改记录')).toBeVisible()
    await expect(card).toHaveCount(0)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
