/**
 * 知识点库 / 公式库「整卡可点」的交互回归。
 *
 * 需求：卡片任意位置点一下就打开详情（不再依赖小小的「查看」按钮），
 * 同时卡片内的操作按钮（编辑/删除/练习/AI 总结）必须仍然各司其职，
 * 不能因为整卡可点而误触「查看」。
 *
 * 注意：UiModal 是 Teleport 到 document.body 的，所以弹窗断言查 document，
 * 卡片本体断言查 wrapper。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const knowledgeRows = [
  {
    id: 1,
    tag_name: '等价无穷小',
    subject_id: 3,
    sub_subject_id: 5,
    summary: '当 $x \\to 0$ 时，$\\sin x \\sim x$。',
    related_tags: ['极限'],
    created_at: '2026-09-01 10:00:00',
  },
  {
    id: 2,
    tag_name: '地址转换',
    subject_id: 4,
    sub_subject_id: 3,
    summary: '页号 + 页内偏移。',
    related_tags: ['分页'],
    created_at: '2026-09-02 10:00:00',
  },
]

const formulaRows = [
  {
    id: 11,
    category: '高等数学',
    title: '基本积分表',
    content: '积分公式正文内容',
    created_at: '2026-09-01 10:00:00',
    updated_at: '2026-09-01 10:00:00',
  },
]

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('../src/api/request', () => {
  const get = vi.fn((url) => {
    if (url === '/knowledge') {
      return Promise.resolve({
        data: { data: { items: knowledgeRows, total: knowledgeRows.length } },
      })
    }
    if (url === '/formulas') {
      return Promise.resolve({ data: { data: formulaRows } })
    }
    return Promise.resolve({ data: { data: [] } })
  })
  return {
    default: {
      get,
      post: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
      put: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
      patch: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
      delete: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    },
  }
})

import KnowledgeView from '../src/views/KnowledgeView.vue'
import FormulaView from '../src/views/FormulaView.vue'

/** 等待挂载后的异步请求与弹窗过渡落地。 */
async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
}

/** Teleport 到 body 的弹窗内容。 */
function bodyText() {
  return document.body.textContent || ''
}

function modalTitles() {
  return Array.from(document.body.querySelectorAll('.modal-title')).map((el) => el.textContent)
}

beforeEach(() => {
  document.body.innerHTML = ''
})

describe('知识点库：整卡可点', () => {
  it('点击卡片命中层打开详情，并渲染完整摘要', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.k-card')
    expect(card.exists()).toBe(true)

    const hit = card.find('.k-hit')
    expect(hit.exists()).toBe(true)
    expect(hit.attributes('aria-label')).toContain('等价无穷小')

    await hit.trigger('click')
    await flush()

    // 详情弹窗（teleport 到 body）已打开并带出标题
    expect(modalTitles().some((t) => t.includes('等价无穷小'))).toBe(true)
    // 全文正文与关联标签都在详情里
    const body = bodyText()
    expect(body).toContain('sin')
    expect(body).toContain('极限')
  })

  it('点「编辑」进编辑态，不会误触详情', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.k-card')
    const editBtn = card.findAll('button').find((b) => b.text().includes('编辑'))
    expect(editBtn).toBeTruthy()

    await editBtn.trigger('click')
    await flush()

    expect(modalTitles().some((t) => t.includes('编辑知识点'))).toBe(true)
    // 不应同时弹出详情
    expect(modalTitles().some((t) => t.includes('等价无穷小'))).toBe(false)
  })

  it('点「练习」跳转复习，不打开任何弹窗', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.k-card')
    const practiceBtn = card.findAll('button').find((b) => b.text().includes('练习'))
    await practiceBtn.trigger('click')
    await flush()

    expect(modalTitles().length).toBe(0)
  })
})

describe('公式库：整卡可点', () => {
  it('点击卡片命中层打开详情并渲染公式内容', async () => {
    const wrapper = mount(FormulaView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.formula-card')
    expect(card.exists()).toBe(true)

    const hit = card.find('.f-hit')
    expect(hit.exists()).toBe(true)
    expect(hit.attributes('aria-label')).toContain('基本积分表')

    await hit.trigger('click')
    await flush()

    expect(modalTitles().some((t) => t.includes('基本积分表'))).toBe(true)
    expect(bodyText()).toContain('积分公式正文内容')
  })

  it('点「删除」只弹确认框，不打开公式详情', async () => {
    const wrapper = mount(FormulaView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.formula-card')
    const delBtn = card.findAll('button').find((b) => b.text().includes('删除'))
    await delBtn.trigger('click')
    await flush()

    expect(modalTitles().some((t) => t.includes('基本积分表'))).toBe(false)
  })
})
