/**
 * 错题详情 → 按标签直通练习（「练这些题」）。
 *
 * 钉住两件事：
 * 1. 按钮**只在同知识点真有错题时**出现（空列表还给人点 = 点了练不到题）；
 * 2. 带的 tag 必须是详情里那条错题的首个标签 —— 后端的 related_mistakes 就是按
 *    `knowledge_tags[0]` 聚的（get_mistake_detail），按钮带的标签若不同，
 *    "看到的这批题"和"练到的那批题"就不是同一批。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const { push } = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useRouter: () => ({ push }), useRoute: () => ({ query: {} }) }
})

const DETAIL = {
  id: 42,
  question: '设 $f(x)$ 在 $[a,b]$ 连续',
  question_type: 'choice',
  knowledge_tags: ['中值定理', '极限'],
  related_mistakes: [
    { id: 43, question: '罗尔定理的条件', subject_id: 1 },
    { id: 44, question: '拉格朗日中值定理的使用范围', subject_id: 1 },
  ],
  knowledge_extra: null,
  related_knowledge: [],
}

const RELATED = { id: 43, question: '罗尔定理的条件', subject_id: 1 }

describe('RelatedList 的「练这些题」', () => {
  let RelatedList

  beforeEach(async () => {
    push.mockClear()
    RelatedList = (await import('../src/components/RelatedList.vue')).default
  })

  function openRelatedPanel(wrapper) {
    const head = wrapper.findAll('.collapse-head').find((b) => b.text().includes('同知识点错题'))
    head.trigger('click')
    return wrapper.vm.$nextTick()
  }

  it('有同知识点错题且有标签时出现，点击带出该标签', async () => {
    const wrapper = mount(RelatedList, {
      props: { relatedMistakes: [RELATED], currentTag: '中值定理' },
    })
    await openRelatedPanel(wrapper)
    const btn = wrapper.findAll('button').find((b) => b.text().includes('练这些题'))
    expect(btn, '按钮没渲染').toBeTruthy()
    expect(btn.text()).toContain('练这些题')
    await btn.trigger('click')
    expect(wrapper.emitted('practice-tag')).toEqual([['中值定理']])
  })

  it('没有同知识点错题时不给按钮（点了也练不到题）', async () => {
    const wrapper = mount(RelatedList, { props: { relatedMistakes: [], currentTag: '中值定理' } })
    await openRelatedPanel(wrapper)
    expect(wrapper.text()).toContain('暂无同知识点错题')
    expect(wrapper.findAll('button').some((b) => b.text().includes('练这些题'))).toBe(false)
  })

  it('有错题但取不到标签时同样不给按钮', async () => {
    const wrapper = mount(RelatedList, { props: { relatedMistakes: [RELATED], currentTag: '' } })
    await openRelatedPanel(wrapper)
    expect(wrapper.findAll('button').some((b) => b.text().includes('练这些题'))).toBe(false)
  })
})

describe('MistakeDetailModal 的按标签直通练习', () => {
  let MistakeDetailModal

  beforeEach(async () => {
    push.mockClear()
    vi.resetModules()
    vi.doMock('../src/api/request', () => ({
      default: {
        get: vi.fn((url) =>
          Promise.resolve({
            data: { data: url.endsWith('/reviews') ? [] : DETAIL },
          }),
        ),
        post: vi.fn(() => Promise.resolve({ data: {} })),
      },
    }))
    MistakeDetailModal = (await import('../src/components/MistakeDetailModal.vue')).default
  })

  async function mountDetail() {
    const wrapper = mount(MistakeDetailModal, {
      props: { modelValue: true, mistakeId: 42 },
      global: { stubs: { RouterLink: true } },
    })
    for (let i = 0; i < 6; i += 1) await Promise.resolve()
    await wrapper.vm.$nextTick()
    return wrapper
  }

  it('点「练这些题」跳到 /review?mode=curve&count=10&tag=首个标签', async () => {
    const wrapper = await mountDetail()
    // 详情弹窗 teleport 到 body，只能在 document 里找
    const head = Array.from(document.querySelectorAll('.collapse-head')).find((b) =>
      b.textContent.includes('同知识点错题'),
    )
    expect(head, '详情没渲染出联动区').toBeTruthy()
    head.click()
    await wrapper.vm.$nextTick()

    const btn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent.includes('练这些题'),
    )
    expect(btn, '联动区没给出「练这些题」').toBeTruthy()
    btn.click()
    await wrapper.vm.$nextTick()

    expect(push).toHaveBeenCalledWith({
      path: '/review',
      query: { mode: 'curve', count: 10, tag: '中值定理' },
    })
  })

  it('无标签的错题不出现该按钮（首个标签为空时列表本来也是空的）', async () => {
    const mod = await import('../src/api/request')
    mod.default.get.mockImplementation((url) =>
      Promise.resolve({
        data: {
          data: url.endsWith('/reviews')
            ? []
            : { ...DETAIL, knowledge_tags: [], related_mistakes: [] },
        },
      }),
    )
    await mountDetail()
    const head = Array.from(document.querySelectorAll('.collapse-head')).find((b) =>
      b.textContent.includes('同知识点错题'),
    )
    head.click()
    await new Promise((r) => setTimeout(r, 0))
    expect(
      Array.from(document.querySelectorAll('button')).some((b) =>
        b.textContent.includes('练这些题'),
      ),
    ).toBe(false)
  })
})
