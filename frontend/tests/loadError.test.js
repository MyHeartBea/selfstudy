/**
 * 「加载失败」与「暂无数据」必须是两个状态。
 *
 * 回归的动机：这几页原本只有 `v-else-if="!items.length"` 一条分支，
 * 请求失败（拦截器只弹一条 3 秒 toast）会掉进「暂无数据」，
 * 用户以为库是空的 —— 错题库那次更是把 loadError 用上了却漏在
 * useMistakeFilters 的解构里，错误 UI 永远渲染不出来。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const get = vi.fn((url) => {
  if (url === '/knowledge' || url === '/formulas' || url === '/vocab') {
    return Promise.reject(new Error('Network Error'))
  }
  return Promise.resolve({ data: { data: { items: [], total: 0 } } })
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('../src/api/request', () => ({
  default: {
    get: (...args) => get(...args),
    post: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    put: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    patch: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    delete: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
  },
}))

import KnowledgeView from '../src/views/KnowledgeView.vue'
import FormulaView from '../src/views/FormulaView.vue'
import VocabView from '../src/views/VocabView.vue'

/** v-reveal 由 main.js 全局注册，单测里没有 app，得自己补一个桩，否则满屏 warning。 */
const mountOpts = {
  attachTo: document.body,
  global: { directives: { reveal: { mounted() {}, updated() {}, unmounted() {} } } },
}

async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function failedLoads() {
  return get.mock.calls.filter((c) => String(c[0]).startsWith('/knowledge')).length
}

beforeEach(() => {
  document.body.innerHTML = ''
  get.mockClear()
})

describe('加载失败态', () => {
  it('知识点库取数失败时显示失败态而不是「暂无知识点」', async () => {
    const wrapper = mount(KnowledgeView, mountOpts)
    await flush()

    const err = wrapper.find('.load-error')
    expect(err.exists()).toBe(true)
    expect(err.text()).toContain('知识点加载失败')
    expect(wrapper.find('.empty').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('暂无知识点')
  })

  it('失败态里的「重新加载」会再打一次请求', async () => {
    const wrapper = mount(KnowledgeView, mountOpts)
    await flush()
    const before = failedLoads()

    const btn = wrapper.findAll('.load-error button').at(-1)
    await btn.trigger('click')
    await flush()

    expect(failedLoads()).toBeGreaterThan(before)
    // 重试仍失败：留在失败态，不会退回空态
    expect(wrapper.find('.load-error').exists()).toBe(true)
  })

  it('公式库取数失败时显示失败态', async () => {
    const wrapper = mount(FormulaView, mountOpts)
    await flush()

    expect(wrapper.find('.load-error').text()).toContain('公式加载失败')
    expect(wrapper.text()).not.toContain('暂无公式')
  })

  it('生词本取数失败时显示失败态', async () => {
    const wrapper = mount(VocabView, mountOpts)
    await flush()

    expect(wrapper.find('.load-error').text()).toContain('生词本加载失败')
    expect(wrapper.text()).not.toContain('生词本还是空的')
  })
})
