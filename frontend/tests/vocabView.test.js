/**
 * 生词本页（此前 1523 行零单测）。
 * 钉两件最容易回归的事：
 * 1. 列表真的把生词渲染出来（不是只有请求发出去）；
 * 2. 加载失败走 UiLoadError（不掉进"生词本还是空的"空态 —— 那会把"没加载出来"
 *    说成"没有生词"），且点重试会真的重新拉一次。
 */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get } }))

import VocabView from '../src/views/VocabView.vue'

function okEnvelope(data, message = 'success') {
  return { data: { code: 200, data, message } }
}

const ROW = {
  id: 1,
  word: 'abandon',
  meaning: '放弃；抛弃',
  phonetic: '/əˈbændən/',
  example: '',
  note: '',
  kind: 'word',
  mastery_level: 2,
  next_review_at: null,
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: defineComponent({ render: () => null }) }],
  })
}

async function mountView() {
  const router = makeRouter()
  const wrapper = mount(VocabView, {
    global: { plugins: [router], stubs: { RouterLink: true } },
    attachTo: document.body,
  })
  await router.isReady()
  for (let i = 0; i < 8; i += 1) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
  return wrapper
}

describe('VocabView', () => {
  it('把生词渲染成卡片（词、释义可见），而不是只发请求', async () => {
    get.mockImplementation((url) => {
      if (url === '/vocab') {
        return Promise.resolve(okEnvelope({ items: [ROW], total: 1, page: 1, page_size: 20 }))
      }
      if (url === '/vocab/stats') {
        return Promise.resolve(
          okEnvelope({ total: 12, due: 4, mastered: 3, distribution: [{ mastery: 2, count: 1 }] }),
        )
      }
      if (url === '/vocab/due') return Promise.resolve(okEnvelope({ items: [], total: 0 }))
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('abandon')
    expect(wrapper.text()).toContain('放弃；抛弃')
    wrapper.unmount()
  })

  it('加载失败走 UiLoadError 并可重试，不掉进空态', async () => {
    get.mockImplementation((url) => {
      if (url === '/vocab') return Promise.reject(new Error('boom'))
      return Promise.resolve(okEnvelope({ items: [], total: 0 }))
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('生词本加载失败')
    expect(wrapper.text()).not.toContain('生词本还是空的')

    const before = get.mock.calls.filter(([u]) => u === '/vocab').length
    get.mockImplementation((url) => {
      if (url === '/vocab') {
        return Promise.resolve(okEnvelope({ items: [ROW], total: 1, page: 1, page_size: 20 }))
      }
      return Promise.resolve(okEnvelope({ items: [], total: 0 }))
    })
    const retry = wrapper.findAll('button').find((b) => b.text().includes('重新加载'))
    expect(retry).toBeTruthy()
    await retry.trigger('click')
    for (let i = 0; i < 8; i += 1) await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
    const after = get.mock.calls.filter(([u]) => u === '/vocab').length
    expect(after).toBeGreaterThan(before)
    expect(wrapper.text()).toContain('abandon')
    wrapper.unmount()
  })
})
