/**
 * 知识点弹窗（KnowledgeEditModal）的交互回归。
 *
 * 需求来源（用户反馈）：
 * 1. 以前粘贴一张图就立刻开始分析，想粘多张时很别扭 → 现在多图先暂存，点「分析图片」才一起分析；
 * 2. 保存后再点「添加知识点」，上一题的内容还留在弹窗里 → 现在打开即重置。
 *
 * 两个测试注意点：
 * - UiModal 用 Teleport 挂到 document.body，所以弹窗内部一律查 document；
 * - 弹窗按「打开」状态挂载粘贴监听，测试要走 false→true 的真实打开流程
 *   （组件若以 modelValue=true 直接挂载，走的是另一条路径，另有专门用例覆盖）。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// vi.mock 会被提升到文件顶部，mock 函数必须用 vi.hoisted 先建好
const { post } = vi.hoisted(() => ({
  post: vi.fn(() => Promise.resolve({ data: { data: {} } })),
}))

vi.mock('../src/api/request', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { data: [] } })),
    post,
    put: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    patch: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
    delete: vi.fn(() => Promise.resolve({ data: { code: 200 } })),
  },
}))

import KnowledgeEditModal from '../src/components/KnowledgeEditModal.vue'

let wrapper = null

async function flush() {
  for (let i = 0; i < 4; i++) await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
}

/** 造一个最小 File（happy-dom 下 FileReader 可读 data URL）。 */
function makeImageFile(name = 'shot.png') {
  return new File(['fake-image-bytes'], name, { type: 'image/png' })
}

/** 模拟一次携带 N 张图片的 Ctrl+V 粘贴。 */
function pasteImages(files) {
  const event = new Event('paste', { bubbles: true, cancelable: true })
  event.clipboardData = { files, items: [] }
  window.dispatchEvent(event)
}

/** 弹窗内的元素查询（全部走 document，因为弹窗 teleport 到 body）。 */
const $ = (sel) => document.body.querySelector(sel)
const $$ = (sel) => Array.from(document.body.querySelectorAll(sel))

const thumbs = () => $$('.img-thumb:not(.img-add)')

function btnByText(text) {
  return $$('button').find((b) => (b.textContent || '').includes(text))
}

async function click(el) {
  el.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await flush()
}

/** 挂载后以 false→true 打开弹窗（模拟点「添加知识点」）。 */
async function mountAndOpen(props = {}) {
  wrapper = mount(KnowledgeEditModal, {
    props: { modelValue: false, row: null, isCreate: false, ...props },
    attachTo: document.body,
  })
  await flush()
  await wrapper.setProps({ modelValue: true })
  await flush()
  return wrapper
}

beforeEach(() => {
  post.mockClear()
  post.mockImplementation(() => Promise.resolve({ data: { data: {} } }))
})

afterEach(() => {
  // 必须 unmount 而不是清 innerHTML：直接清空会让 Vue 的 Teleport 记账错乱
  if (wrapper) {
    wrapper.unmount()
    wrapper = null
  }
})

describe('知识点弹窗：多图暂存后再分析', () => {
  it('同时粘贴多张图片会被全部暂存，并且不立刻调用 AI', async () => {
    await mountAndOpen({ isCreate: true })

    pasteImages([makeImageFile('a.png'), makeImageFile('b.png'), makeImageFile('c.png')])
    await flush()
    await flush()

    // 三张都进了暂存区（旧实现只会留下第一张）
    expect(thumbs().length).toBe(3)
    expect(document.body.textContent).toContain('已暂存 3 张')
    // 关键：粘贴本身不触发分析
    expect(post).not.toHaveBeenCalled()
  })

  it('连续多次粘贴会累加，不互相覆盖', async () => {
    await mountAndOpen({ isCreate: true })

    pasteImages([makeImageFile('a.png')])
    await flush()
    await flush()
    pasteImages([makeImageFile('b.png')])
    await flush()
    await flush()

    expect(thumbs().length).toBe(2)
  })

  it('点「分析图片」时把全部暂存图片一次提交给后端', async () => {
    post.mockImplementation(() =>
      Promise.resolve({
        data: { data: { tag_name: '等价无穷小', summary: '摘要', related_tags: ['极限'] } },
      }),
    )
    await mountAndOpen({ isCreate: true })

    pasteImages([makeImageFile('a.png'), makeImageFile('b.png')])
    await flush()
    await flush()

    const analyzeBtn = btnByText('分析图片')
    expect(analyzeBtn).toBeTruthy()
    await click(analyzeBtn)
    await flush()

    expect(post).toHaveBeenCalledTimes(1)
    const [url, payload] = post.mock.calls[0]
    expect(url).toBe('/ai/knowledge-from-image')
    expect(Array.isArray(payload.images)).toBe(true)
    expect(payload.images.length).toBe(2)
    // base64 纯数据，不带 data: 前缀
    expect(String(payload.images[0]).startsWith('data:')).toBe(false)

    // 草稿回填到表单
    expect($('input[placeholder*="等价无穷小"]').value).toBe('等价无穷小')
  })

  it('可以单独移除某一张暂存图片', async () => {
    await mountAndOpen({ isCreate: true })

    pasteImages([makeImageFile('a.png'), makeImageFile('b.png')])
    await flush()
    await flush()
    expect(thumbs().length).toBe(2)

    await click($('.img-del'))
    expect(thumbs().length).toBe(1)
  })

  it('没有暂存图片时「分析图片」按钮不可点', async () => {
    await mountAndOpen({ isCreate: true })
    expect(btnByText('分析图片').hasAttribute('disabled')).toBe(true)
  })

  it('弹窗直接以打开状态挂载时，粘贴依然生效（防回归）', async () => {
    // 父组件若提前把 modelValue 置真，监听必须照样挂上，不能静默失效
    wrapper = mount(KnowledgeEditModal, {
      props: { modelValue: true, isCreate: true, row: null },
      attachTo: document.body,
    })
    await flush()

    pasteImages([makeImageFile('a.png')])
    await flush()
    await flush()

    expect(thumbs().length).toBe(1)
  })
})

describe('知识点弹窗：保存后重新打开不再残留', () => {
  it('保存 → 关闭 → 再打开添加，表单清空且不再有上一张图', async () => {
    await mountAndOpen({ isCreate: true })

    pasteImages([makeImageFile('a.png')])
    await flush()
    await flush()
    expect(thumbs().length).toBe(1)

    // 手填名称与摘要（模拟 AI 回填后的核对）
    const nameInput = $('input[placeholder*="等价无穷小"]')
    nameInput.value = '旧知识点'
    nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    const summary = $('textarea')
    summary.value = '旧的摘要内容'
    summary.dispatchEvent(new Event('input', { bubbles: true }))
    await flush()

    await click(btnByText('添加'))
    await flush()

    // 关闭再打开
    await wrapper.setProps({ modelValue: false })
    await flush()
    await wrapper.setProps({ modelValue: true })
    await flush()

    expect($('input[placeholder*="等价无穷小"]').value).toBe('')
    expect($('textarea').value).toBe('')
    expect(thumbs().length).toBe(0)
  })

  it('编辑模式下打开会载入该行内容（重置逻辑不能把编辑数据清掉）', async () => {
    const row = {
      id: 9,
      tag_name: '地址转换',
      subject_id: 4,
      sub_subject_id: 3,
      summary: '页号 + 页内偏移',
      related_tags: ['分页'],
    }
    await mountAndOpen({ row, isCreate: false })

    const nameInput = $('input[name="knowledge_tag_name"]')
    expect(nameInput.value).toBe('地址转换')
    expect(nameInput.disabled).toBe(true) // 编辑模式不允许改名称
    expect($('textarea').value).toBe('页号 + 页内偏移')
  })
})
