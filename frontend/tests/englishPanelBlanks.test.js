/**
 * 完形空位标记的可视化 + 长列表折叠（EnglishAnalysisPanel）。
 *
 * 完形录入重构后，原文 passage_text 里保留 __N__ 空位标记、每空一题。
 * 钉住：空位标记要高亮成可点击的 token（.ep-blank），点击跳到对应小题
 * （#ep-q-N 锚点）——完形 20 题逐题对答案时靠它快速定位。
 *
 * 折叠（用户实测反馈：20 题全铺开非常冗长）：≥4 题默认收起成
 * 「答案 + 题干一行」摘要（.ep-q-brief），点击展开单题；「全部展开」一键铺开；
 * 点空位跳题时目标题自动展开。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('../src/api/request', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

import EnglishAnalysisPanel from '../src/components/EnglishAnalysisPanel.vue'

const PARSED = {
  question: 'They are ____ more at home.',
  correct_answer: 'B',
  question_type: 'choice',
  passage_text: 'They are __1__ more at home. Research shows __2__ people earn more.',
  english_sentences: [
    { text: 'They are __1__ more at home.', translation: '他们在家更放松。' },
    { text: 'Research shows __2__ people earn more.', translation: '研究表明快乐的人挣得更多。' },
  ],
  english_questions: [
    {
      question: 'Research shows ____ people earn more.',
      correct_answer: 'C',
      question_type: 'choice',
    },
  ],
}

// 六题的完形（≥4 触发折叠）
function bigParsed(count) {
  const passage = Array.from({ length: count }, (_, i) => `Sentence ${i + 1} has __${i + 1}__ gap.`)
    .map((s, i) => (i % 2 ? s : s + ' Extra context here.'))
    .join(' ')
  const questions = Array.from({ length: count }, (_, i) => ({
    question: `Sentence ${i + 1} has ____ gap.`,
    correct_answer: 'ABCD'[i % 4],
    question_type: 'choice',
    analysis: `解析 ${i + 1}`,
  }))
  return {
    question: questions[0].question,
    correct_answer: questions[0].correct_answer,
    question_type: 'choice',
    passage_text: passage,
    english_sentences: [{ text: passage, translation: '译文' }],
    english_questions: questions.slice(1),
  }
}

describe('EnglishAnalysisPanel 完形空位', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('空位标记渲染成高亮 token，不在原文里丢失', () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: PARSED } })
    // 原文对照 + 句子拆解两处都渲染，每处 2 个标记
    expect(wrapper.findAll('button.ep-blank').length).toBeGreaterThanOrEqual(4)
    // 标记显示为原始文本（__1__），不是被吞掉或替换
    expect(wrapper.findAll('button.ep-blank').some((b) => b.text().includes('1'))).toBe(true)
    // 空位不算可查义词
    expect(wordButtons(wrapper, '1')).toHaveLength(0)
  })

  it('点击空位跳到对应小题（#ep-q-N）', async () => {
    // 跳转走 document.getElementById，组件必须真挂到文档上
    const wrapper = mount(EnglishAnalysisPanel, {
      props: { parsed: PARSED },
      attachTo: document.body,
    })
    const blanks = wrapper.findAll('button.ep-blank')
    await blanks[0].trigger('click')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    // 跳转目标是第 1 空对应的小题锚点
    expect(wrapper.find('#ep-q-1').exists()).toBe(true)
    expect(wrapper.find('#ep-q-2').exists()).toBe(true)
    wrapper.unmount()
  })

  function wordButtons(wrapper, text) {
    return wrapper.findAll('button.ep-word').filter((b) => b.text().trim() === text)
  }
})

describe('EnglishAnalysisPanel 长列表折叠', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('少于 4 题不折叠，行为与旧版一致', () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: PARSED } })
    expect(wrapper.find('button.ep-q-brief').exists()).toBe(false)
    expect(wrapper.find('.ep-question-text').isVisible()).toBe(true)
  })

  // 注意：此 happy-dom 版本的 getComputedStyle 不回读内联 style，VTU 的
  // isVisible 对 v-show 恒真 —— 折叠断言直接查内联 display
  const hiddenBodies = (wrapper) =>
    wrapper.findAll('.ep-q-body').filter((b) => b.element.style.display === 'none').length

  it('完形 6 题默认收起成摘要行：答案印章+题干一行，正文隐藏', () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: bigParsed(6) } })
    const briefs = wrapper.findAll('button.ep-q-brief')
    expect(briefs).toHaveLength(6)
    // 摘要行带答案字母与题干预览
    expect(briefs[1].text()).toContain('B')
    expect(briefs[1].text()).toContain('Sentence 2 has ____ gap.')
    // 正文默认隐藏（v-show display:none）
    expect(wrapper.find('#ep-q-2 .ep-q-body').element.style.display).toBe('none')
    // 「全部展开」按钮显示已收起数量
    expect(wrapper.find('button.ep-q-fold-all').text()).toContain('已收起 6 题')
  })

  it('点摘要行展开单题；「全部展开」后全部可见可再收起', async () => {
    const wrapper = mount(EnglishAnalysisPanel, { props: { parsed: bigParsed(6) } })
    await wrapper.findAll('button.ep-q-brief')[2].trigger('click')
    expect(wrapper.find('#ep-q-3 .ep-q-body').element.style.display).toBe('')
    expect(hiddenBodies(wrapper)).toBe(5)

    await wrapper.find('button.ep-q-fold-all').trigger('click')
    expect(hiddenBodies(wrapper)).toBe(0)
    await wrapper.find('button.ep-q-fold-all').trigger('click')
    expect(hiddenBodies(wrapper)).toBe(6)
  })

  it('点空位跳题：目标题折叠时自动展开再滚动', async () => {
    const wrapper = mount(EnglishAnalysisPanel, {
      props: { parsed: bigParsed(6) },
      attachTo: document.body,
    })
    expect(wrapper.find('#ep-q-5 .ep-q-body').element.style.display).toBe('none')
    // 第 5 空的空位标记在原文里，点击后 #ep-q-5 应展开
    const blank5 = wrapper.findAll('button.ep-blank').find((b) => b.text().includes('5'))
    await blank5.trigger('click')
    expect(wrapper.find('#ep-q-5 .ep-q-body').element.style.display).toBe('')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    wrapper.unmount()
  })
})
