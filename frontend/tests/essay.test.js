/**
 * 英语作文批改链路的前端回归：
 *  1) wordDiff 逐词对比（改错展示的地基）；
 *  2) EssayGradeResult 真渲染出分数/档位/diff/范文折叠；
 *  3) EssayPanel 点「开始批改」真的打到 /essays/grade、结果渲染出来、
 *     「存入错题库」真的带着批改摘要 POST /mistakes。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import { wordDiff, wordDiffStats } from '../src/utils/essayDiff.js'

const GRADE_RESULT = {
  kind: 'e2_long',
  kind_name: '英语二 大作文（图表作文 15 分）',
  max_score: 15,
  score: 11,
  band: '第四档',
  dimensions: { content: 5, structure: 2, language: 3, format: 1 },
  estimated_word_count: 152,
  corrections: [
    {
      original: 'The number of students go up.',
      corrected: 'The number of students goes up.',
      type: '主谓一致',
      note: 'the number of 作主语谓语用单数',
    },
  ],
  highlights: ['定语从句 which 用得自然'],
  overall: '整体第四档，要点齐全。',
  top_errors: ['主谓一致'],
  weakness_advice: '专练三单。',
  upgrade_tips: ['I think it is important -> It is widely acknowledged that...'],
  model_version: 'As is vividly shown in the chart.',
  raw_transcript: 'The number of students go up.',
}

describe('wordDiff', () => {
  it('标出替换词并保持顺序', () => {
    const parts = wordDiff('The number go up', 'The numbers go up')
    expect(parts).toEqual([
      { type: 'same', text: 'The' },
      { type: 'del', text: 'number' },
      { type: 'ins', text: 'numbers' },
      { type: 'same', text: 'go up' },
    ])
  })

  it('标点差异不算改动（home. vs home）', () => {
    expect(wordDiffStats('He go home.', 'He goes home').changed).toBe(2) // go->goes 两处 del+ins
    expect(wordDiffStats('He goes home.', 'He goes home').changed).toBe(0)
  })

  it('空句与整句重写', () => {
    expect(wordDiff('', 'a b')).toEqual([{ type: 'ins', text: 'a b' }])
    expect(wordDiff('a b', '')).toEqual([{ type: 'del', text: 'a b' }])
    expect(wordDiff('', '')).toEqual([])
  })
})

describe('EssayGradeResult', () => {
  async function mountResult(props = {}) {
    const mod = await import('../src/components/EssayGradeResult.vue')
    return mount(mod.default, {
      props: { result: GRADE_RESULT, transcript: GRADE_RESULT.raw_transcript, ...props },
    })
  }

  it('渲染分数、档位、四维与逐句改错的 del/ins', async () => {
    const wrapper = await mountResult()
    expect(wrapper.find('.er-score').text()).toBe('11')
    expect(wrapper.text()).toContain('15')
    expect(wrapper.text()).toContain('第四档')
    expect(wrapper.text()).toContain('内容要点')
    const item = wrapper.find('.er-corr-item')
    expect(item.find('.d-del').text()).toContain('go')
    expect(item.find('.d-ins').text()).toContain('goes')
    expect(item.text()).toContain('主谓一致')
    expect(wrapper.findAll('.er-list li').length).toBeGreaterThan(1)
    // 范文默认折叠
    expect(wrapper.find('.er-model').exists()).toBe(false)
  })

  it('折叠区点击后才展开转录与范文', async () => {
    const wrapper = await mountResult()
    const toggles = wrapper.findAll('.er-toggle')
    expect(toggles.length).toBe(2)
    await toggles[0].trigger('click')
    expect(wrapper.find('.er-model').text()).toContain('As is vividly shown')
    await toggles[1].trigger('click')
    expect(wrapper.find('.er-transcript').text()).toContain('go up')
  })

  it('无 transcript 时不出现核对区', async () => {
    const wrapper = await mountResult({ transcript: '' })
    expect(wrapper.findAll('.er-toggle').length).toBe(1)
  })
})

describe('EssayPanel', () => {
  const calls = []

  beforeEach(() => {
    calls.length = 0
    vi.resetModules()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.doMock('../src/api/request', () => ({
      default: {
        post: vi.fn((url, body) => {
          calls.push({ url, body })
          if (url === '/essays/grade') {
            return Promise.resolve({ data: { data: { ...GRADE_RESULT } } })
          }
          if (url === '/mistakes') {
            return Promise.resolve({ data: { data: { id: 99 } } })
          }
          return Promise.resolve({ data: { data: {} } })
        }),
        get: vi.fn((url) => {
          calls.push({ url })
          if (url === '/subjects') {
            return Promise.resolve({ data: { data: [{ id: 2, name: '英语（二）' }] } })
          }
          if (url === '/sub_subjects') {
            return Promise.resolve({ data: { data: [{ id: 11, name: '写作' }] } })
          }
          return Promise.resolve({ data: { data: [] } })
        }),
      },
    }))
  })

  async function mountPanel() {
    const mod = await import('../src/components/EssayPanel.vue')
    return mount(mod.default, {
      global: { stubs: { RouterLink: true } },
      props: {},
    })
  }

  it('缺内容时不发请求，只提示', async () => {
    const wrapper = await mountPanel()
    await wrapper.find('.ep-actions .btn-primary').trigger('click')
    await wrapper.vm.$nextTick()
    expect(calls.filter((c) => c.url === '/essays/grade').length).toBe(0)
  })

  it('粘贴文本 → 批改 → 渲染结果 → 存入错题库带上批改摘要', async () => {
    const wrapper = await mountPanel()
    const textareas = wrapper.findAll('textarea')
    await textareas[0].setValue('Write an essay about the chart.')
    await textareas[1].setValue(GRADE_RESULT.raw_transcript)

    await wrapper.find('.ep-actions .btn-primary').trigger('click')
    await vi.waitFor(() => {
      expect(calls.some((c) => c.url === '/essays/grade')).toBe(true)
    })
    const gradeCall = calls.find((c) => c.url === '/essays/grade')
    expect(gradeCall.body.kind).toBe('e2_long')
    expect(gradeCall.body.prompt_text).toBe('Write an essay about the chart.')

    await vi.waitFor(() => {
      expect(wrapper.find('.er-score').exists()).toBe(true)
    })
    expect(wrapper.find('.er-score').text()).toBe('11')
    expect(wrapper.text()).toContain('已存档到作文档案')

    const saveButtons = wrapper.findAll('.ep-result-actions button')
    await saveButtons[0].trigger('click')
    await vi.waitFor(() => {
      expect(calls.some((c) => c.url === '/mistakes')).toBe(true)
    })
    const mistake = calls.find((c) => c.url === '/mistakes').body
    expect(mistake.subject_id).toBe(2)
    expect(mistake.sub_subject_id).toBe(11)
    expect(mistake.question_type).toBe('solution')
    expect(mistake.question).toBe('Write an essay about the chart.')
    expect(mistake.analysis).toContain('逐句改错')
    expect(mistake.analysis).toContain('goes up')
    expect(mistake.knowledge_tags).toContain('英语作文')
  })

  it('批改失败时展示后端原因并可重试', async () => {
    const wrapper = await mountPanel()
    const mod = await import('../src/api/request')
    mod.default.post.mockImplementationOnce((url) => {
      calls.push({ url })
      return Promise.reject({ response: { data: { message: 'AI 余额不足' } }, status: 502 })
    })
    await wrapper.findAll('textarea')[1].setValue('some essay')
    await wrapper.find('.ep-actions .btn-primary').trigger('click')
    await vi.waitFor(() => {
      expect(wrapper.find('.ep-error').exists()).toBe(true)
    })
    expect(wrapper.find('.ep-error').text()).toContain('AI 余额不足')
  })
})
