/**
 * 启动页（校准台）单测 —— 对齐 atlas 参考稿后的行为
 *
 * 旧测试失败的原因**不是代码坏了**，而是它断言的是旧契约：
 *   旧版：rest → inking → opening 三段 + 圆形遮罩揭幕
 *   新版：00 → 100 缓出计数 1250ms + 三行阶段点亮 + **整块向上抽走** translateY(-101%)
 * 所以这里断言新契约，而不是迁就旧断言。
 */
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import InkLoader from '../src/app/InkLoader.vue'

/** 用假定时器驱动组件内部的 requestAnimationFrame 循环 */
function rafWithFakeTimers() {
  let id = 0
  const cbs = new Map()
  globalThis.requestAnimationFrame = (cb) => {
    id += 1
    cbs.set(id, cb)
    return id
  }
  globalThis.cancelAnimationFrame = (i) => cbs.delete(i)
  return {
    /** 推进一帧并 flush DOM（rAF 改了 ref，DOM 要等 nextTick 才更新） */
    async tick(ms = 16) {
      vi.advanceTimersByTime(ms)
      const run = [...cbs.entries()]
      cbs.clear()
      run.forEach(([, cb]) => cb(performance.now()))
      await nextTick()
    },
  }
}

describe('InkLoader 校准台', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // 关键：让 performance.now() 跟着**假定时器**走。
    // 组件用真实时间差计算进度（这是对的产品行为，因为帧率不可控）；
    // 所以测试必须 mock 时间源，而不是让组件去迁就假定时器。
    vi.spyOn(performance, 'now').mockImplementation(() => vi.getMockedSystemTime() ?? Date.now())
    document.body.style.overflow = ''
    document.body.classList.remove('ready')
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.style.overflow = ''
    document.body.classList.remove('ready')
  })

  it('挂载即锁滚动，并显示两位读数与三行阶段', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    expect(document.body.style.overflow).toBe('hidden')
    expect(w.find('.num').text()).toBe('00')
    expect(w.findAll('.steps span')).toHaveLength(3)
    await f.tick()
    w.unmount()
  })

  it('计数随时间增长（缓出），且当前阶段被点亮', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    for (let i = 0; i < 32; i++) await f.tick(16) // 约 500ms / 1250ms
    const mid = Number(w.find('.num').text())
    expect(mid).toBeGreaterThan(0)
    expect(mid).toBeLessThan(100)
    expect(w.findAll('.steps span.on')).toHaveLength(1)
    w.unmount()
  })

  it('走完后加 .done（触发向上抽走）、解锁滚动、标记 body.ready', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    for (let i = 0; i < 100; i++) await f.tick(16)
    await vi.advanceTimersByTimeAsync(220) // finish() 内的 160ms 延迟
    expect(w.find('.loader').classes()).toContain('done')
    expect(document.body.style.overflow).toBe('')
    expect(document.body.classList.contains('ready')).toBe(true)
    expect(w.find('.num').text()).toBe('100')
    w.unmount()
  })

  it('抽走 1200ms 后才 emit done（保留转场观感，不瞬间消失）', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    for (let i = 0; i < 100; i++) await f.tick(16)
    await vi.advanceTimersByTimeAsync(220)
    expect(w.emitted('done')).toBeFalsy()
    await vi.advanceTimersByTimeAsync(1300)
    expect(w.emitted('done')).toHaveLength(1)
    w.unmount()
  })

  it('任意键可跳过：直接到 100 并抽走', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    f.tick(16)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await w.vm.$nextTick()
    expect(w.find('.num').text()).toBe('100')
    expect(w.find('.loader').classes()).toContain('done')
    w.unmount()
  })

  it('rAF 被节流（完全不触发）时，进度仍由兜底定时器推进并正常结束', async () => {
    // 这是本次修的真问题：无头/后台标签页里 rAF 可能 3 秒只触发几次，
    // 靠它驱动时长动画会卡住。现在时间来源是 Date.now + 100ms 兜底定时器。
    rafWithFakeTimers() // 只装 rAF 桩；本用例刻意**不**执行它
    const w = mount(InkLoader)
    // 只推进定时器，不执行 rAF 回调 —— 模拟 rAF 被完全节流
    for (let i = 0; i < 16; i++) {
      await vi.advanceTimersByTimeAsync(100)
      await nextTick()
    }
    expect(w.find('.num').text()).toBe('100')
    expect(w.find('.loader').classes()).toContain('done')
    w.unmount()
  })

  it('卸载时解锁滚动（异常路径不锁死页面）', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    f.tick(16)
    w.unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('可访问性：progressbar 语义 + 阶段文本对辅助技术隐藏', async () => {
    const f = rafWithFakeTimers()
    const w = mount(InkLoader)
    expect(w.attributes('role')).toBe('progressbar')
    expect(w.attributes('aria-label')).toBe('正在校准观测站')
    expect(w.find('.steps').attributes('aria-hidden')).toBe('true')
    await f.tick()
    w.unmount()
  })
})
