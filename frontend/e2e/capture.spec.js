/**
 * 智能录入（/capture）关键路径 —— 真浏览器回归。
 *
 * 背景（真实事故）：粘贴多张截图时只保留了最后一张。原因是
 * `for (const f of accepted) { stageImage(await fileToDataUrl(f)) }`
 * 在循环里 await，回调解析时循环变量已走到末尾，于是每张图都被当成最后一张。
 * 修复是「先全部暂存，再一次分析」。这类 bug 单测只能造假事件对象，
 * 这里用浏览器原生 ClipboardEvent + DataTransfer 真实复现粘贴。
 *
 * 同时验证三点：**不自动分析**、**只发一次请求**、**请求体带齐全部图片**。
 */
import {
  test,
  expect,
  mockApi,
  pasteImage,
  pickImageByTestId,
  callsTo,
  guardPageErrors,
  expectAllApiStubbed,
  withMessage,
} from './fixtures.js'

/**
 * /api/ai/english 的假响应。
 *
 * ⚠️ **字段名必须是接口响应的形状，不是 LLM 的入参形状** —— 真正的规整逻辑在
 * `backend/app/services/ai_english.py:normalize_english_parsed`：
 * 输入 `passage/translation/sentences/phrases/words/questions`，输出
 * `passage_text/passage_translation/english_sentences/english_phrases/english_words/english_questions`
 * （`is_english` 由 `routers/ai.py` 注入）。
 * 早先这里照抄了入参名字，导致 `EnglishAnalysisPanel` 的 `paragraphs`/`bilingual`
 * 全为空、`.ep-bilingual` 压根不渲染 —— 解析结果的渲染链路等于没人验。
 */
const fakeEnglishResult = {
  is_english: true,
  passage_text: 'This is a passage.',
  passage_translation: '这是一段文章。',
  english_sentences: [{ text: 'This is a passage.', translation: '这是一段文章。' }],
  english_phrases: [],
  english_words: [],
  english_questions: [],
  question_type: 'choice',
  method: 'vision',
}

test.describe('智能录入 · 图片暂存与一次分析', () => {
  test('连续粘贴 3 张只暂存、不自动分析；点按钮后只发一次且带齐 3 张图，结果正常渲染', async ({
    page,
  }) => {
    const errors = guardPageErrors(page)
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

    // **同步点放在「结果已渲染」而不是「请求已发出」**：
    // 只 poll 请求次数的话，采样到 1 的瞬间就会放行；"响应回来后才触发的第二次请求"
    // 也永远观察不到（测试随即结束）。先等真实渲染结果，再在终态数请求。
    //
    // 这几条断言做过变异验证：把夹具里的 `passage_text` 改名后，`.ep-bilingual` 不再渲染、
    // 面板退回「（未识别到原文内容）」，此用例立刻失败 —— 即断言真的在验渲染链路，
    // 而不是"只要请求发了就算过"。
    const panel = page.locator('.english-learn')
    await expect(panel).toBeVisible()
    await expect(panel.locator('.ep-bilingual')).toBeVisible()
    await expect(panel.locator('.ep-bi-cn').first()).toContainText('这是一段文章。')

    const englishCalls = callsTo(calls, '/api/ai/english')
    expect(englishCalls, '整场只应发一次英语解析请求').toHaveLength(1)
    expect(englishCalls[0].body.images).toHaveLength(3)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('「选择图片」入口：只暂存不自动分析（选中即主图，追加走粘贴）', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, { '/api/ai/english': fakeEnglishResult })
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()

    // 主图 input 走 data-testid，不受 DOM 顺序/文案影响
    await pickImageByTestId(page, 'pick-main-image', { name: 'picked-1.png', rgb: [255, 0, 0] })
    await expect(page.locator('.image-preview img')).toBeVisible()
    // 注意：选中图片走的就是"主图"分支，第二张起只能靠粘贴追加 ——
    // 追加区（.more-images）此时不渲染是**正确行为**，不要断言它存在。
    await expect(page.locator('.more-images')).toHaveCount(0)
    expect(callsTo(calls, '/api/ai/english')).toHaveLength(0)

    await page.getByRole('button', { name: '开始识别并解析' }).click()
    await expect(page.locator('.english-learn')).toBeVisible()

    const englishCalls = callsTo(calls, '/api/ai/english')
    expect(englishCalls).toHaveLength(1)
    expect(englishCalls[0].body.images).toHaveLength(1)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('没有图片时「开始识别并解析」不可用', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page)
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()

    // 未暂存图片时该按钮不渲染（v-if="previewImage"），因此不可能误触发请求
    await expect(page.getByRole('button', { name: '开始识别并解析' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '手动整理' }).first()).toBeVisible()

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})

test.describe('智能录入 · 视觉通道降级提醒', () => {
  // 视觉通道按序回退：首选通道报错会被兜底通道的成功掩盖，识别"照样出结果、只是又慢又抖"。
  // 后端把原因写在响应的 message 里，前端 CaptureView 只在含"已降级"时挂提醒条。
  // 这条链路单测摸不到（要 mount 整个 CaptureView 并打桩七八个接口），
  // 而且真实事故形态恰恰是"什么都没坏、只是悄悄变慢"，所以在这里钉住渲染结果。
  const degradedMessage = '英语整篇解析完成（首选通道 stale-vision-model 失败，已降级）'

  test('首选通道失败退到兜底：结果照常渲染，同时把降级原因显示成提醒', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, {
      '/api/ai/english': withMessage({ ...fakeEnglishResult, method: 'vision' }, degradedMessage),
    })
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()
    await pickImageByTestId(page, 'pick-main-image', { name: 'degraded.png' })
    await page.getByRole('button', { name: '开始识别并解析' }).click()

    // 同步点放在"结果已渲染"：降级不许把识别结果一起弄丢
    await expect(page.locator('.english-learn')).toBeVisible()
    const warn = page.locator('.notice.warn')
    await expect(warn).toBeVisible()
    await expect(warn).toContainText('已降级')
    await expect(warn).toContainText('stale-vision-model', '提醒要写明是哪个通道挂了')

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })

  test('首选通道正常返回时不显示降级提醒', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, { '/api/ai/english': fakeEnglishResult })
    await page.goto('/capture')
    await page.getByRole('tab', { name: '上传图片' }).click()
    await pickImageByTestId(page, 'pick-main-image', { name: 'normal.png' })
    await page.getByRole('button', { name: '开始识别并解析' }).click()

    await expect(page.locator('.english-learn')).toBeVisible()
    // 反向也要钉：默认 message('success') 里不含"已降级"，提醒条不该出现
    await expect(page.locator('.notice.warn')).toHaveCount(0)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
