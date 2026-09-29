/**
 * VocabFlashcard 会话逻辑单测(663 行交互件此前裸奔):
 * 1) 判分锁——快速连按只发一次请求(flyDir + grading 双守卫);
 * 2) 随机回队——"不认识"回队 2 份、"模糊"回队 1 次封顶(会话可终止);
 * 3) keep-alive 生命周期——deactivated 摘除 window 键盘监听。
 * request 层整体 mock;YearRing 打桩(其 canvas 在 happy-dom 下无 2d 上下文)。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { KeepAlive } from 'vue'

const h0 = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get: h0.get, post: h0.post } }))

import VocabFlashcard from '../src/components/VocabFlashcard.vue'

const CARDS = [
  { id: 1, word: 'apple', meaning: '苹果', mastery_level: 0 },
  { id: 2, word: 'banana', meaning: '香蕉', mastery_level: 0 },
]

function okEnvelope(data) {
  return Promise.resolve({ data: { code: 200, data, message: 'success' } })
}

async function flush() {
  for (let i = 0; i < 8; i += 1) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

function press(key) {
  window.dispatchEvent(new KeyboardEvent('keydown', { key }))
}

async function mountCard() {
  const { mount } = await import('@vue/test-utils')
  const wrapper = mount(VocabFlashcard, {
    attachTo: document.body,
    global: { stubs: { YearRing: true } },
  })
  await flush()
  return wrapper
}

function reviewPosts() {
  return h0.post.mock.calls.filter(([u]) => u.startsWith('/vocab/'))
}

describe('VocabFlashcard 会话逻辑', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    h0.get.mockImplementation((url) => {
      if (url === '/vocab/due') return okEnvelope(CARDS.map((c) => ({ ...c })))
      if (/\/vocab\/\d+\/context/.test(url)) return okEnvelope([])
      return Promise.reject(new Error(`unexpected GET ${url}`))
    })
    h0.post.mockImplementation(() => okEnvelope({ mastery_level: 1 }))
  })

  it('判分锁:连按两下数字键只发一次请求', async () => {
    const wrapper = await mountCard()
    press(' ') // 翻面
    press('1') // 不认识 → grade 开始,POST 在途
    press('1') // 在途锁必须拦下第二次
    await flush()
    expect(reviewPosts()).toHaveLength(1)
    wrapper.unmount()
  })

  it('不认识:随机回队 2 份,再次判不认识仍会再插,直到全会', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5) // 固定随机,插入位置可预期
    const wrapper = await mountCard()
    press(' ') // 翻 A
    press('1') // A 不认识 → 回队 2 份 → 队列 [B, A, A]
    await flush()
    press(' ') // 翻 B
    press('3') // B 认识
    await flush()
    press(' ') // 翻 A(第一份回队)
    press('3')
    await flush()
    press(' ') // 翻 A(第二份回队)
    press('3')
    await flush()
    const posts = reviewPosts()
    expect(posts).toHaveLength(4) // A 不认识 ×1 + B 认识 ×1 + A 认识 ×2
    expect(posts.filter(([, b]) => b.result === 'unknown')).toHaveLength(1)
    expect(wrapper.emitted('done')).toBeTruthy() // 全会 → 会话结束
    wrapper.unmount()
  })

  it('模糊:回队 1 次封顶,再次判模糊不再插队,会话可终止', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    const wrapper = await mountCard()
    press(' ') // 翻 A
    press('ArrowDown') // A 模糊 → 回队 1 份(flyGrade 延迟 240ms)
    await new Promise((r) => setTimeout(r, 280))
    press(' ') // 翻 B
    press('ArrowDown') // B 模糊 → 回队 1 份
    await new Promise((r) => setTimeout(r, 280))
    press(' ') // 翻 A(回队份)
    press('ArrowDown') // A 再次模糊 → 上限,不再插队
    await new Promise((r) => setTimeout(r, 280))
    press(' ') // 翻 B(回队份)
    press('ArrowDown') // B 再次模糊 → 上限 → 会话结束(模糊不死循环)
    await new Promise((r) => setTimeout(r, 280))
    const fuzzyPosts = reviewPosts().filter(([, b]) => b.result === 'fuzzy')
    expect(fuzzyPosts).toHaveLength(4) // A/B 各判两次
    expect(wrapper.emitted('done')).toBeTruthy()
    wrapper.unmount()
  })

  it('keep-alive 生命周期:deactivated 摘除 window 键盘监听,activated 重新挂上', async () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const addSpy = vi.spyOn(window, 'addEventListener')
    const show = ref(true)
    const host = defineComponent({
      setup() {
        return () => h(KeepAlive, null, () => (show.value ? h(VocabFlashcard) : h('div')))
      },
    })
    const { mount } = await import('@vue/test-utils')
    const wrapper = mount(host, { attachTo: document.body })
    await flush()
    const addsBefore = addSpy.mock.calls.filter(([e]) => e === 'keydown').length
    expect(addsBefore).toBeGreaterThan(0)

    show.value = false // 触发 deactivated
    await nextTick()
    await flush()
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function))

    show.value = true // 重新激活:监听必须回来
    await nextTick()
    await flush()
    const addsAfter = addSpy.mock.calls.filter(([e]) => e === 'keydown').length
    expect(addsAfter).toBeGreaterThan(addsBefore)

    wrapper.unmount()
  })
})
