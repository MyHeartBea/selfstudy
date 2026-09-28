/**
 * 知识点复习（SM-2 与错题同源调度）在 KnowledgeView 里的整条 UI 链路：
 * ①「复习知识点」拉队列 → 有到期才开弹窗（没有到期只提示，不开空弹窗）；
 * ②「显示摘要」前只露名字（回忆优先），自评后该条出队、下一条顶上；
 * ③评完队列清空出完成页。
 */
import { describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get, post } }))

import KnowledgeView from '../src/views/KnowledgeView.vue'

function okEnvelope(data, message = 'success') {
  return { data: { code: 200, data, message } }
}

const QUEUE_ROW = {
  id: 11,
  tag_name: '泰勒公式',
  summary: '用多项式逼近函数，注意余项。',
  related_tags: ['中值定理'],
  subject_name: '数学二',
  review_count: 0,
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
  const wrapper = mount(KnowledgeView, {
    global: { plugins: [router], stubs: { RouterLink: true } },
    attachTo: document.body,
  })
  await router.isReady()
  await flushPromises()
  return wrapper
}

describe('KnowledgeView 知识点复习', () => {
  it('有到期知识点：弹窗先只露名字，显示摘要后自评出队', async () => {
    get.mockImplementation((url) => {
      if (url === '/knowledge') {
        return Promise.resolve(okEnvelope({ items: [QUEUE_ROW], total: 1, page: 1, page_size: 9 }))
      }
      if (url === '/knowledge/tags') return Promise.resolve(okEnvelope([]))
      if (url === '/knowledge/review/queue') {
        return Promise.resolve(okEnvelope({ items: [QUEUE_ROW], dueTotal: 1, returned: 1 }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    post.mockImplementation((url) => {
      if (url === '/knowledge/11/review') {
        return Promise.resolve(okEnvelope({ ...QUEUE_ROW, review_count: 1 }))
      }
      return Promise.reject(new Error(`unexpected POST ${url}`))
    })

    const wrapper = await mountView()
    // 复习弹窗 Teleport 到 body，弹窗内按钮要用 document 级查询（wrapper 里看不到）
    const bodyButtons = () => [...document.querySelectorAll('button')]
    await bodyButtons()
      .find((b) => b.textContent.includes('复习知识点'))
      .click()
    await flushPromises()

    const modal = document.querySelector('.modal-panel')
    expect(modal).toBeTruthy()
    expect(modal.textContent).toContain('泰勒公式')
    // 回忆优先：摘要没点显示前不许剧透
    expect(modal.textContent).not.toContain('多项式逼近')

    await bodyButtons()
      .find((b) => b.textContent.includes('显示摘要'))
      .click()
    expect(document.querySelector('.modal-panel').textContent).toContain('多项式逼近')

    await bodyButtons()
      .find((b) => b.textContent.trim() === '记住了')
      .click()
    await flushPromises()
    expect(post).toHaveBeenCalledWith('/knowledge/11/review', { result: true })
    // 该条出队 → 完成页
    expect(document.querySelector('.modal-panel').textContent).toContain('本轮复习完成')
    wrapper.unmount()
  })

  it('没有到期：只提示，不开弹窗', async () => {
    get.mockImplementation((url) => {
      if (url === '/knowledge') {
        return Promise.resolve(okEnvelope({ items: [], total: 0, page: 1, page_size: 9 }))
      }
      if (url === '/knowledge/tags') return Promise.resolve(okEnvelope([]))
      if (url === '/knowledge/review/queue') {
        return Promise.resolve(okEnvelope({ items: [], dueTotal: 0, returned: 0 }))
      }
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    const wrapper = await mountView()
    await [...document.querySelectorAll('button')]
      .find((b) => b.textContent.includes('复习知识点'))
      .click()
    await flushPromises()
    expect(document.querySelector('.modal-panel')).toBeNull()
    wrapper.unmount()
  })
})
