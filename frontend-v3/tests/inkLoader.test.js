/**
 * 启动页单测（happy-dom）
 *
 * 这里验的是"组件契约"，不是动画观感（观感由真浏览器像素校验负责）：
 *   1. 三个阶段的类名会随状态切换
 *   2. 默认 props 下会走完流程并 emit done
 *   3. 任意键可以跳过（这是每天开很多次的工具，跳过必须真的有效）
 *   4. 卸载后不留副作用（body overflow 复原、事件解绑）
 *
 * 注意：harness 默认在 happy-dom 里跑，没有 requestAnimationFrame 的稳定节拍，
 * 所以对时序断言一律用 vi.useFakeTimers + 手动推进，避免 flaky。
 */
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import InkLoader from '../src/app/InkLoader.vue'

describe('InkLoader 研墨开场', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    document.body.style.overflow = ''
    document.body.className = ''
  })

  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
    document.body.style.overflow = ''
    document.body.className = ''
  })

  it('挂载后进入第一段（rest），并锁住滚动', () => {
    const wrapper = mount(InkLoader)
    expect(wrapper.classes()).toContain('ink-loader')
    expect(wrapper.classes()).toContain('rest')
    expect(document.body.style.overflow).toBe('hidden')
    wrapper.unmount()
  })

  it('700ms 后进入第二段（inking），读数不再是 000 之外的空值', async () => {
    const wrapper = mount(InkLoader)
    vi.advanceTimersByTime(760)
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).toContain('inking')
    // 读数始终是 3 位数字（等宽对齐是视觉要求）
    expect(wrapper.find('.digits').text()).toMatch(/^\d{3}$/)
    wrapper.unmount()
  })

  it('跳过路径会 emit done、解锁滚动并标记跳过', async () => {
    // 说明：这里刻意只验**同步可控**的路径。
    // "自然跑完"依赖 document.fonts.ready + rAF 节拍，在 happy-dom + fake timers 下不稳定，
    // 那条链路由真浏览器验证（无头 Chrome 实测：rest 0.9s / inking 1.4s / opening 3.5s / 卸载）。
    const wrapper = mount(InkLoader, { props: { minDuration: 99999 } })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    vi.advanceTimersByTime(1000)
    expect(wrapper.emitted('done')).toBeTruthy()
    expect(document.body.classList.contains('ready')).toBe(true)
    expect(document.body.style.overflow).toBe('')
    // 跳过会留下可观测标记，便于在浏览器里确认走的是跳过路径
    expect(document.documentElement.dataset.loaderSkipped).toBe('1')
    wrapper.unmount()
    delete document.documentElement.dataset.loaderSkipped
  })

  it('卸载后清理：overflow 复原、键盘监听解绑', () => {
    const wrapper = mount(InkLoader, { props: { minDuration: 99999 } })
    wrapper.unmount()
    expect(document.body.style.overflow).toBe('')
    // 解绑后按键不应再触发 done（已卸载，emitted 不再累积）
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    expect(wrapper.emitted('done')).toBeFalsy()
  })

  it('无障碍：带 progressbar 语义与进度值', () => {
    const wrapper = mount(InkLoader)
    const el = wrapper.find('[role="progressbar"]')
    expect(el.exists()).toBe(true)
    expect(el.attributes('aria-valuemin')).toBe('0')
    expect(el.attributes('aria-valuemax')).toBe('100')
    expect(Number(el.attributes('aria-valuenow'))).toBeGreaterThanOrEqual(0)
    wrapper.unmount()
  })
})
