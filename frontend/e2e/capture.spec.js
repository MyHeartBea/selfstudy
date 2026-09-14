/**
 * 智能录入（/capture）关键路径 —— 真浏览器回归。
 *
 * 背景（真实事故）：粘贴多张截图时只保留了最后一张。原因是
 * `for (const f of accepted) { stageImage(await fileToDataUrl(f)) }`
 * 在循环里 await，回调解析时循环变量已走到末尾，于是每张图都被当成最后一张。
 * 修复是「先全部暂存，再一次分析」。这类 bug 单测只能造假事件对象，
 * 这里用浏览器原生 ClipboardEvent + DataTransfer 真实复现粘贴。
 *
 * 同时验证：**分析只发一次请求**，且请求体里带着全部已暂存的图片 ——
 * 这正是"暂存而不是每贴一张就分析一次"的契约。
 */
import { test, expect, mockApi, pasteImage, pickImageByTestId, callsTo } from './fixtures.js'

/** /api/ai/english 的假响应：结构按 AiEnglishResult 的最小可用子集。 */
const fakeEnglishResult = {
  is_english: true,
  passage: 'This is a passage.',
  translation: '这是一段文章。',
  sentences: [],
  phrases: [],
  words: [],
  questions: [],
  images: [],
  method: 'vision',
}

test.describe('智能录入 · 图片暂存与一次分析', () => {
  test('连续粘贴 3 张只暂存、不自动分析，点「开始识别并解析」才发且只发一次请求', async ({
    page,
  }) => {
    const calls = await mockApi(page, { '/api/ai/english': fakeEnglishResult })
    await page.goto('/capture')

    // 切到图片 Tab（UiTabs 用 role="tab"）
    await page.getByRole('tab', { name: '上传图片' }).click()
    await expect(page.getByRole('tab', { name: '上传图片' })).toHaveAttribute(
      'aria-selected',
      'true',
    )

    // 第 1 张：成为主图（出现预览与"下一张粘贴为"控件）
    await pasteImage(page, { name: 'a.png', rgb: [255, 0, 0] })
    await expect(page.locator('.image-preview img')).toBeVisible()
    await expect(page.locator('.paste-target-row')).toBeVisible()

    // 第 2、3 张：追加暂存，不能触发任何分析请求
    await pasteImage(page, { name: 'b.png', rgb: [0, 255, 0] })
    await pasteImage(page, { name: 'c.png', rgb: [0, 0, 255] })
    await expect(page.locator('.more-image-item')).toHaveCount(2)
    expect(callsTo(calls, '/api/ai/english')).toHaveLength(0)

    // 全部图片都还在（事故时这里会只剩最后一张）
    await expect(page.locator('.image-preview img')).toHaveCount(1)
    const previewSrc = await page.locator('.image-preview img').getAttribute('src')
    const moreSrcs = await page
      .locator('.more-image-item img')
      .evaluateAll((els) => els.map((el) => el.getAttribute('src')))
    expect(previewSrc).toBeTruthy()
    expect(moreSrcs.filter(Boolean)).toHaveLength(2)
    expect(new Set([previewSrc, ...moreSrcs]).size).toBe(3)

    await page.getByRole('button', { name: '开始识别并解析' }).click()

    await expect.poll(() => callsTo(calls, '/api/ai/english').length, { timeout: 10_000 }).toBe(1)
    const [call] = callsTo(calls, '/api/ai/english')
    expect(call.body.images).toHaveLength(3)
  })

  test('「选择图片」入口：只暂存不自动分析', async ({ page }) => {
    const calls = await mockApi(page, { '/api/ai/english': fakeEnglishResult })
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()

    // 主图 input 走 data-testid，不受 DOM 顺序/文案影响
    await pickImageByTestId(page, 'pick-main-image', { name: 'picked-1.png', rgb: [255, 0, 0] })
    await expect(page.locator('.image-preview img')).toBeVisible()
    // 暂存完不能自动分析：必须等用户点「开始识别并解析」
    expect(callsTo(calls, '/api/ai/english')).toHaveLength(0)

    await page.getByRole('button', { name: '开始识别并解析' }).click()
    await expect.poll(() => callsTo(calls, '/api/ai/english').length, { timeout: 10_000 }).toBe(1)
    expect(callsTo(calls, '/api/ai/english')[0].body.images).toHaveLength(1)
  })

  test('没有图片时「开始识别并解析」不可用', async ({ page }) => {
    await mockApi(page)
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()

    // 未暂存图片时该按钮不渲染（v-if="previewImage"），因此不可能误触发请求
    await expect(page.getByRole('button', { name: '开始识别并解析' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '手动整理' }).first()).toBeVisible()
  })
})
