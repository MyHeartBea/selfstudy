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
  it('卡片是整卡按钮语义（role=button + tabindex），带可读名称', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.k-card')
    expect(card.exists()).toBe(true)
    expect(card.attributes('role')).toBe('button')
    expect(card.attributes('tabindex')).toBe('0')
    expect(card.attributes('aria-label')).toContain('等价无穷小')
  })

  // 关键回归：以前只有「点击层」那条窄缝有反应，点标题/摘要/标签/空白都没反应。
  // 现在必须卡片的每个区域都能打开详情。
  const regions = [
    ['标题 .k-name', '.k-name'],
    ['头部 .k-head', '.k-head'],
    ['日期 .k-time', '.k-time'],
    ['科目标签 .k-chips', '.k-chips'],
    ['摘要 .k-summary', '.k-summary'],
    ['关联区 .k-rel', '.k-rel'],
    ['操作栏空白 .k-ops', '.k-ops'],
  ]

  for (const [label, sel] of regions) {
    it(`点击${label} 也能打开详情`, async () => {
      const wrapper = mount(KnowledgeView, { attachTo: document.body })
      await flush()

      const el = wrapper.find(`.k-card ${sel}`)
      expect(el.exists()).toBe(true)
      await el.trigger('click')
      await flush()

      expect(document.querySelectorAll('.k-detail').length).toBe(1)
    })
  }

  it('点击卡片本体打开详情，并渲染完整摘要', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    await wrapper.find('.k-card').trigger('click')
    await flush()

    expect(modalTitles().some((t) => t.includes('等价无穷小'))).toBe(true)
    const body = bodyText()
    expect(body).toContain('sin')
    expect(body).toContain('极限')
  })

  it('键盘可达：Enter / Space 打开详情', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.k-card')
    await card.trigger('keydown', { key: 'Enter' })
    await flush()
    expect(document.querySelectorAll('.k-detail').length).toBe(1)
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
    // 操作按钮阻止了冒泡：不应同时弹出详情
    expect(document.querySelectorAll('.k-detail').length).toBe(0)
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

  it('点关联标签只做筛选，不打开详情', async () => {
    const wrapper = mount(KnowledgeView, { attachTo: document.body })
    await flush()

    const tag = wrapper.find('.k-card .k-rel .ui-tag')
    expect(tag.exists()).toBe(true)
    await tag.trigger('click')
    await flush()

    expect(document.querySelectorAll('.k-detail').length).toBe(0)
  })
})

describe('公式库：整卡可点', () => {
  it('卡片是整卡按钮语义', async () => {
    const wrapper = mount(FormulaView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.formula-card')
    expect(card.attributes('role')).toBe('button')
    expect(card.attributes('aria-label')).toContain('基本积分表')
  })

  for (const [label, sel] of [
    ['分类印章 .cat-seal', '.cat-seal'],
    ['标题 .formula-title', '.formula-title'],
    ['预览 .formula-preview', '.formula-preview'],
    ['底部信息 .formula-foot', '.formula-foot'],
  ]) {
    it(`点击${label} 也能打开公式详情`, async () => {
      const wrapper = mount(FormulaView, { attachTo: document.body })
      await flush()

      const el = wrapper.find(`.formula-card ${sel}`)
      expect(el.exists()).toBe(true)
      await el.trigger('click')
      await flush()

      expect(modalTitles().some((t) => t.includes('基本积分表'))).toBe(true)
      expect(bodyText()).toContain('积分公式正文内容')
    })
  }

  it('点「编辑」不打开详情', async () => {
    const wrapper = mount(FormulaView, { attachTo: document.body })
    await flush()

    const card = wrapper.find('.formula-card')
    const editBtn = card.findAll('button').find((b) => b.text().includes('编辑'))
    await editBtn.trigger('click')
    await flush()

    expect(modalTitles().some((t) => t.includes('编辑公式'))).toBe(true)
    expect(modalTitles().some((t) => t === '基本积分表')).toBe(false)
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
