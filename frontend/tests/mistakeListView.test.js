/**
 * 错题列表页（此前 1013 行零单测）。
 * 特别钉 loadError：**这个视图当年就翻过车** —— useMistakeFilters 早就返回了
 * loadError，但视图解构时漏了它，错误 UI 永远渲染不出来且三道关卡全绿
 * （AGENTS 6.5「踩过的坑」）。这条用例保证它不再静默消失。
 */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get } }))

import MistakeListView from '../src/views/MistakeListView.vue'

function okEnvelope(data, message = 'success') {
  return { data: { code: 200, data, message } }
}

const ROW = {
  id: 7,
  question: '设函数 f(x)=x^2 在区间上连续，求极值',
  question_type: 'choice',
  subject_id: 1,
  difficulty: 3,
  starred: false,
  knowledge_tags: '导数',
  images: [],
  created_at: '2026-09-20 10:00:00',
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: defineComponent({ render: () => null }) }],
  })
}

async function mountView() {
  const router = makeRouter()
  const wrapper = mount(MistakeListView, {
    global: { plugins: [router], stubs: { RouterLink: true } },
    attachTo: document.body,
  })
  await router.isReady()
  for (let i = 0; i < 8; i += 1) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
  return wrapper
}

describe('MistakeListView', () => {
  it('把错题渲染出来（题干可见）', async () => {
    get.mockImplementation((url) => {
      if (url === '/mistakes') {
        return Promise.resolve(okEnvelope({ items: [ROW], total: 1, page: 1, page_size: 6 }))
      }
      if (url === '/subjects') return Promise.resolve(okEnvelope([]))
      if (url === '/sub_subjects') return Promise.resolve(okEnvelope([]))
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('设函数 f(x)=x^2 在区间上连续，求极值')
    wrapper.unmount()
  })

  it('加载失败走 UiLoadError（可重试），不掉进"还没有错题"的空态', async () => {
    get.mockImplementation((url) => {
      if (url === '/mistakes') return Promise.reject(new Error('boom'))
      return Promise.resolve(okEnvelope([]))
    })
    const wrapper = await mountView()
    expect(wrapper.text()).toContain('加载失败')

    get.mockImplementation((url) => {
      if (url === '/mistakes') {
        return Promise.resolve(okEnvelope({ items: [ROW], total: 1, page: 1, page_size: 6 }))
      }
      return Promise.resolve(okEnvelope([]))
    })
    const retry = wrapper.findAll('button').find((b) => b.text().includes('重新加载'))
    expect(retry).toBeTruthy()
    await retry.trigger('click')
    for (let i = 0; i < 8; i += 1) await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
    expect(wrapper.text()).toContain('设函数 f(x)=x^2 在区间上连续，求极值')
    wrapper.unmount()
  })
})
