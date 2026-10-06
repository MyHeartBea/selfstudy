/**
 * 完形空位标记的可视化（EnglishAnalysisPanel）。
 *
 * 完形录入重构后，原文 passage_text 里保留 __N__ 空位标记、每空一题。
 * 钉住：空位标记要高亮成可点击的 token（.ep-blank），点击跳到对应小题
 * （#ep-q-N 锚点）——完形 20 题逐题对答案时靠它快速定位。
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
