/**
 * 模考多科连考（paper_ids）—— 单测覆盖不到的整卷链路。
 *
 * 连考 = PracticeView 勾多卷 → /review?mode=mock&paper_ids=11,12：
 * 两卷题目按序拼成一张卷面、共用倒计时；交卷统一判分后，
 * 成绩单按卷小计，答错的题按**各自所属卷**的科目/年份/卷名归档进错题本。
 * 单卷（paper_id）行为由既有用例与单测兜住，这里只钉连考新增的三件事：
 * 拼接渲染、分卷小计、按卷归档。
 */
import { test, expect, mockApi, guardPageErrors, expectAllApiStubbed, callsTo } from './fixtures.js'

const paper11 = {
  id: 11,
  status: 'done',
  title: '2021 数学二真题',
  year: '2021',
  subject: '数学二',
  questions: [
    {
      id: 801,
      no: 1,
      section: '选择题',
      question_type: 'choice',
      question: '设 $f(x)=x^2$，则 $f(1)$ 等于',
      option_a: '0',
      option_b: '1',
      option_c: '2',
      option_d: '3',
      correct_answer: 'B',
      analysis: '代入即可',
    },
  ],
}
const paper12 = {
  id: 12,
  status: 'done',
  title: '2020 英语二真题',
  year: '2020',
  subject: '英语二',
  questions: [
    {
      id: 802,
      no: 1,
      section: '完形填空',
      question_type: 'choice',
      question: 'He ____ the answer immediately.',
      option_a: 'knew',
      option_b: 'knows',
      option_c: 'known',
      option_d: 'knowing',
      correct_answer: 'A',
      analysis: '时态：过去时。',
    },
  ],
}

test.describe('模考多科连考', () => {
  test('两卷拼接共用倒计时，交卷后分卷小计、错题按各自卷归档', async ({ page }) => {
    const errors = guardPageErrors(page)
    const calls = await mockApi(page, {
      '/api/papers/11': paper11,
      '/api/papers/12': paper12,
    })
    await page.goto('/review?mode=mock&duration=60&paper_ids=11,12')

    await expect(page.locator('.mock-timer')).toBeVisible()
    // 第 1 题来自数学卷，卷头带各自卷名（count-tip 在页面别处也有，须圈定题卡）
    const qMeta = page.locator('.stage-card .detail-meta .count-tip').first()
    await expect(qMeta).toContainText('2021 数学二真题')
    await page.locator('.option-row').nth(1).click() // B，答对

    // 第 2 题来自英语卷：换卷后卷名跟着换，阅读原文不许从上一卷漏过来
    await page.getByRole('button', { name: '下一题' }).click()
    await expect(qMeta).toContainText('2020 英语二真题')
    await page.locator('.option-row').nth(1).click() // B，答错（正确 A）

    // 交卷：确认弹窗 → 统一判分
    await page.getByRole('button', { name: /交卷（2\/2 已答）/ }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: '交卷' }).click()

    // 成绩单：总分 + 分卷小计（两卷各一行）
    await expect(page.getByText('模考成绩单')).toBeVisible()
    await expect(page.getByText('1/2 正确')).toBeVisible()
    const papersBlock = page.locator('.mr-papers')
    await expect(papersBlock).toContainText('2021 数学二真题')
    await expect(papersBlock).toContainText('1/1 · 100 分')
    await expect(papersBlock).toContainText('2020 英语二真题')
    await expect(papersBlock).toContainText('0/1 · 0 分')

    // 数学卷答错的那题不存在 —— 英语卷答错的才入库：按各自卷的科目/年份/卷名
    const filed = callsTo(calls, '/api/mistakes')
    expect(filed, '英语卷答错 1 题 → 恰好入库 1 条').toHaveLength(1)
    expect(filed[0].body.subject_id).toBe(2) // 英语二 → subjects 里 id=2 的「英语二」
    expect(filed[0].body.source_year).toBe('2020')
    expect(filed[0].body.source_name).toBe('2020 英语二真题')
    expect(filed[0].body.correct_answer).toBe('A')

    // 成绩存档：连考年份合并成标签（统计页趋势用它做横轴说明）
    const archived = callsTo(calls, '/api/mocks')
    expect(archived).toHaveLength(1)
    expect(archived[0].body.exam_year).toBe('2021·2020')
    expect(archived[0].body.total).toBe(2)
    expect(archived[0].body.correct).toBe(1)

    expectAllApiStubbed(calls)
    expect(errors, `页面报错：${errors.join(' | ')}`).toHaveLength(0)
  })
})
