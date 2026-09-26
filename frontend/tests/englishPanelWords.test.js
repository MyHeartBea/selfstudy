/**
 * 英语句内点词 / 点短语（EnglishAnalysisPanel）。
 *
 * 钉两个真实使用反馈：
 * 1. 点词弹窗里「加入生词本」成功后，原文里的这个词要**立刻**变红（known）——
 *    过去只入库不动本地状态，颜色纹丝不动，用户以为没加上；
 * 2. AI 提取的重点短语（english_phrases）在原文里要**整体**成一个可点 token——
 *    过去按单词切分，短语只能一个词一个词点。
 * 短语弹窗直接用已提取释义，**不调 AI**（get 不被触发）。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get, post } }))

import EnglishAnalysisPanel from '../src/components/EnglishAnalysisPanel.vue'

const PARSED = {
  passage_text: 'I look forward to the exam. She threw a glance at me.',
  passage_translation: '我期待这场考试。她瞥了我一眼。',
  english_sentences: [
    {
      text: 'I look forward to the exam.',
      translation: '我期待这场考试。',
      structure: '',
      pattern: '',
    },
    {
      text: 'She threw a glance at me.',
      translation: '她瞥了我一眼。',
      structure: '',
      pattern: '',
    },
  ],
  english_phrases: [{ phrase: 'look forward to', meaning: '期待；盼望', example: '', pos: '' }],
  english_words: [{ word: 'glance', meaning: '一瞥', pos: 'n.', phonetic: '', example: '' }],
  english_questions: [],
}

function wordButtons(wrapper, text) {
  return wrapper.findAll('button.ep-word').filter((b) => b.text().trim() === text)
}

describe('EnglishAnalysisPanel 点词/点短语', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({
      data: {
        code: 200,
        data: {
          word: 'exam',
          phonetic: '',
          meanings: [{ pos: 'n.', meaning: '考试' }],
          example: '',
        },
        message: 'success',
      },
    })
    post.mockResolvedValue({
      data: { code: 200, data: { created: 1, updated: 0 }, message: 'success' },
    })
  })

  it('AI 提取的短语整体成 token，且直接高亮', () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: PARSED } })
    const phrase = wordButtons(wrapper, 'look forward to')
    expect(phrase.length).toBeGreaterThanOrEqual(1)
    expect(phrase[0].classes()).toContain('known')
    // 短语内的单词不再单独出 token
    expect(wordButtons(wrapper, 'forward')).toHaveLength(0)
  })

  it('点词加入生词本后，该词立刻变红', async () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: PARSED } })
    const exam = wordButtons(wrapper, 'exam')[0]
    expect(exam.classes()).not.toContain('known')
    await exam.trigger('click')
    await flushPromises()
    const addBtn = [...document.body.querySelectorAll('button')].find((b) =>
      b.textContent.includes('加入生词本'),
    )
    expect(addBtn).toBeTruthy()
    await addBtn.click()
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post.mock.calls[0][0]).toBe('/vocab/import-english')
    expect(post.mock.calls[0][1].items[0].kind).toBe('word')
    expect(wordButtons(wrapper, 'exam')[0].classes()).toContain('known')
  })

  it('点短语直接用已提取释义，不调 AI 查义', async () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: PARSED } })
    await wordButtons(wrapper, 'look forward to')[0].trigger('click')
    await flushPromises()
    expect(get).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('短语释义')
    expect(document.body.textContent).toContain('期待；盼望')
    const addBtn = [...document.body.querySelectorAll('button')].find((b) =>
      b.textContent.includes('加入生词本'),
    )
    await addBtn.click()
    await flushPromises()
    expect(post.mock.calls[0][1].items[0].kind).toBe('phrase')
  })

  it('详情（readonly）也显示勾选列表，能勾短语加入生词本', async () => {
    // 真实反馈：详情页过去没有勾选入口，用户无法自主选择短语
    const wrapper = mount(EnglishAnalysisPanel, {
      props: { parsed: PARSED, readonly: true },
    })
    const section = wrapper.findAll('.ep-section').find((s) => s.text().includes('猜词'))
    expect(section).toBeTruthy()
    expect(section.text()).toContain('look forward to')
    expect(section.text()).toContain('glance')
    const phraseRow = section
      .findAll('label.ep-vocab-item')
      .find((l) => l.text().includes('look forward to'))
    await phraseRow.find('input[type=checkbox]').setValue()
    const addBtn = section.findAll('button').find((b) => b.text().includes('加入生词本'))
    await addBtn.trigger('click')
    await flushPromises()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post.mock.calls[0][0]).toBe('/vocab/import-english')
    expect(post.mock.calls[0][1].items).toHaveLength(1)
    expect(post.mock.calls[0][1].items[0].kind).toBe('phrase')
    wrapper.unmount()
  })

  it('划选两个词浮出「查短语」，整段查义且入生词本 kind=phrase', async () => {
    // 真实反馈：原文里 turns out 这类未提取短语只能逐词点，看不到整体释义
    vi.spyOn(window, 'getSelection').mockReturnValue({
      toString: () => 'turned out',
      rangeCount: 1,
      getRangeAt: () => ({
        getBoundingClientRect: () => ({ left: 10, top: 100, width: 60, height: 20 }),
      }),
    })
    const wrapper = mount(EnglishAnalysisPanel, {
      props: { parsed: PARSED, readonly: true },
      attachTo: document.body,
    })
    await wrapper.find('.english-panel').trigger('mouseup')
    const btn = wrapper.find('.ep-sel-lookup')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('turned out')
    await btn.trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0][1].params.word).toBe('turned out')
    expect(document.body.textContent).toContain('短语释义')
    const addBtn = [...document.body.querySelectorAll('.modal-foot button')].find((b) =>
      b.textContent.includes('加入生词本'),
    )
    expect(addBtn).toBeTruthy()
    await addBtn.click()
    await flushPromises()
    expect(post.mock.calls[0][1].items[0].kind).toBe('phrase')
    wrapper.unmount()
    vi.restoreAllMocks()
  })

  it('划选把空位 __6__ 剔除；单词划选不出浮钮（点词已有入口）', async () => {
    const wrapper = mount(EnglishAnalysisPanel, {
      props: { parsed: PARSED, readonly: true },
      attachTo: document.body,
    })
    const stubSel = (text) =>
      vi.spyOn(window, 'getSelection').mockReturnValue({
        toString: () => text,
        rangeCount: 1,
        getRangeAt: () => ({
          getBoundingClientRect: () => ({ left: 10, top: 100, width: 60, height: 20 }),
        }),
      })
    stubSel('in terms __6__ of')
    await wrapper.find('.english-panel').trigger('mouseup')
    expect(wrapper.find('.ep-sel-lookup').text()).toContain('in terms of')
    vi.restoreAllMocks()
    stubSel('exam')
    await wrapper.find('.english-panel').trigger('mouseup')
    expect(wrapper.find('.ep-sel-lookup').exists()).toBe(false)
    wrapper.unmount()
  })
})
