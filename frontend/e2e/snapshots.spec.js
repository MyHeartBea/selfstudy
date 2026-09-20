/**
 * 整库回滚的确认门（真浏览器）。
 *
 * 单测（`tests/snapshotsView.test.js`）已经把纯函数、状态机、请求体钉死了，
 * 这里只补它在 happy-dom 里**结构上看不见**的两段：
 * 1. **Enter 提交** —— `ConfirmHost` 的输入框是 `@keyup.enter="confirmOk"`，
 *    单测用 `trigger('click')` 走按钮，永远抓不到"回车把整库覆盖了"这类事故；
 * 2. **Esc 取消** —— 弹窗由 `UiModal` 的全局 keydown 处理，teleport 到 body，
 *    单测里的 wrapper 根本摸不到那条链路。
 *
 * 两条都同时断言"该发请求时恰好一次、不该发时一次都没有"：
 * 这一页按错的代价是整库被覆盖。
 */
import {
  test,
  expect,
  mockApi,
  guardPageErrors,
  expectAllApiStubbed,
  snapshotRows,
} from './fixtures.js'

async function openRestoreDialog(page) {
  await page.getByRole('button', { name: '回滚到这一份' }).first().click()
  await expect(page.locator('.confirm-input')).toBeVisible()
}

test.describe('数据备份与回滚', () => {
  test('输入 RESTORE 后按 Enter 才发起回滚，且只发一次', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/snapshots')
    await expect(page.locator('tbody tr')).toHaveCount(snapshotRows.length)

    await openRestoreDialog(page)
    await page.locator('.confirm-input').fill('RESTORE')
    await page.locator('.confirm-input').press('Enter')

    await expect(page.getByText('刚才回到了')).toBeVisible()
    const posts = calls.filter((c) => c.method === 'POST' && c.path === '/api/snapshots/restore')
    expect(posts).toHaveLength(1)
    // 服务端那道同名校验是最后一道门：confirm 必须逐字等于快照文件名
    expect(posts[0].body).toEqual({ name: snapshotRows[0].name, confirm: snapshotRows[0].name })
    // 结果卡把反悔点写在页面上（只飘一条 toast 的话，用户关掉就找不到那份文件名了）
    await expect(page.getByText('kaoyan_mistakes_20260920_120000_before-restore.db')).toBeVisible()

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('大小写不对时 Enter 不会误发请求，改对了才发', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/snapshots')

    await openRestoreDialog(page)
    await page.locator('.confirm-input').fill('restore')
    await page.locator('.confirm-input').press('Enter')
    // 正向断言：红字出现 + 弹窗仍在（否定断言在元素不存在时也算通过，不能用在这里）
    await expect(page.locator('.confirm-error')).toHaveText(/RESTORE/)
    await expect(page.locator('.confirm-input')).toBeVisible()
    expect(
      calls.filter((c) => c.method === 'POST' && c.path === '/api/snapshots/restore'),
    ).toHaveLength(0)

    await page.locator('.confirm-input').fill('RESTORE')
    await page.locator('.confirm-input').press('Enter')
    await expect(page.getByText('刚才回到了')).toBeVisible()
    expect(
      calls.filter((c) => c.method === 'POST' && c.path === '/api/snapshots/restore'),
    ).toHaveLength(1)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('按 Esc 关掉确认弹窗就什么都不会发生', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/snapshots')

    await openRestoreDialog(page)
    await page.keyboard.press('Escape')
    await expect(page.locator('.confirm-input')).toBeHidden()
    expect(
      calls.filter((c) => c.method === 'POST' && c.path === '/api/snapshots/restore'),
    ).toHaveLength(0)

    // 关掉之后页面还是那份列表（没有被半路改掉的副作用）
    await expect(page.locator('tbody tr')).toHaveCount(snapshotRows.length)
    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('「立刻备份一次」打 POST /api/snapshots', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/snapshots')

    await page.getByRole('button', { name: '立刻备份一次' }).click()
    await expect(page.locator('.toast').first()).toBeVisible()
    const posts = calls.filter((c) => c.method === 'POST' && c.path === '/api/snapshots')
    expect(posts).toHaveLength(1)
    expect(posts[0].url).toContain('label=manual')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
