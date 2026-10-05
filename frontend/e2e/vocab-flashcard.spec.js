/**
 * 生词闪卡会话(浏览器链路)——单测覆盖不到的整链:
 * 开始快刷 → 翻面 → 判分(POST /vocab/{id}/review) → 队列推进 → 全部判完出完成页。
 * 随机回队逻辑(模糊/不认识的重插)由单测固定 Math.random 钉住,这里只走真实按钮链路。
 */
import { test, expect, mockApi, guardPageErrors, callsTo } from './fixtures.js'

async function flushE2e(page) {
  // 判分 POST 是在途 promise,队列推进稍后落地:给一轮微任务+宏任务
  await page.waitForTimeout(120)
}

const dueCards = [
  { id: 1, word: 'grant', meaning: '拨款;授予', example: 'Pell Grants...', mastery_level: 0 },
  { id: 2, word: 'scripted', meaning: '照稿子念的', example: '', mastery_level: 0 },
]

test.describe('生词闪卡会话', () => {
  test('开始快刷 → 翻面 → 判分推进 → 完成页', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, {
      // /vocab/due 返回**纯数组**(get_due_vocab 直接 return items[:limit]),
      // 写成 {items:[]} 会让 start() 把对象当队列 → length undefined → 静默退出
      '/api/vocab/due': dueCards,
      '/api/vocab/quota': { daily_limit: 30 },
      '/api/vocab/1/review': { id: 1 },
      '/api/vocab/2/review': { id: 2 },
    })
    await page.goto('/vocab')

    // 进入快刷会话(入口按钮文案带"开始快刷")
    await page.getByRole('button', { name: /开始快刷/ }).click()
    await expect(page.locator('.flash-stage')).toBeVisible()
    await expect(page.locator('.flash-head .count-tip')).toContainText('1 / 2')

    // 翻面 → 背面出现释义,判分按钮解禁
    await page.locator('.flash-stage').click()
    await expect(page.locator('.flash-meaning')).toContainText('拨款')

    // 判第一张:不认识 → 随机回队 2 份,队列 2→4(计数显示 2 / 4,这是新行为的直接验证)
    await page.locator('.grade-btn.unknown').click()
    await expect(page.locator('.flash-head .count-tip')).toContainText('2 / 4')

    // 判第二张:认识 → 推进到回队的 A
    await page.locator('.flash-stage').click()
    await page.locator('.grade-btn.known').click()
    await expect(page.locator('.flash-head .count-tip')).toContainText('3 / 4')

    // 把回队的 A 判完两次(认识) → 全部判完,完成页出现
    await page.locator('.flash-stage').click()
    await page.locator('.grade-btn.known').click()
    await flushE2e(page)
    await page.locator('.flash-stage').click()
    await page.locator('.grade-btn.known').click()
    await expect(page.locator('.flash-done')).toContainText('本轮快刷完成')

    // 判分真实落库:card1 = 1 不认识 + 2 认识,card2 = 1 认识
    const reviews1 = await callsTo(calls, '/api/vocab/1/review')
    expect(reviews1).toHaveLength(3)
    const reviews2 = await callsTo(calls, '/api/vocab/2/review')
    expect(reviews2).toHaveLength(1)
    expect(errors).toEqual([])
  })
})
