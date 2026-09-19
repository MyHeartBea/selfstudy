/**
 * 难度星级（ui/UiStars.vue）的键盘可达性。
 *
 * 为什么单独测：表单里「难度」是必填项，而改之前整组是 role="img" + 裸 @click 的 span，
 * 没有 tabindex —— 只用键盘的人 Tab 得完全跳过它，提交时卡在必填校验上无处可去。
 * 这类"点得动但按不到"的死角，鼠标测试永远看不见。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UiStars from '../src/ui/UiStars.vue'

function mountStars(props = {}, options = {}) {
  return mount(UiStars, { props, ...options })
}

function radios(w) {
  return w.findAll('[role="radio"]')
}

describe('UiStars 键盘操作', () => {
  it('交互模式：radiogroup + 五个 radio，组内只有一个 Tab 落点', () => {
    const w = mountStars({ modelValue: 3 })
    expect(w.attributes('role')).toBe('radiogroup')
    const rs = radios(w)
    expect(rs).toHaveLength(5)
    expect(rs.filter((r) => r.attributes('tabindex') === '0')).toHaveLength(1)
    expect(rs[2].attributes('tabindex')).toBe('0')
    expect(rs[2].attributes('aria-checked')).toBe('true')
    expect(rs[1].attributes('aria-checked')).toBe('false')
  })

  it('未评分（0）时第 1 颗星承接焦点，键盘用户不会掉出组外', () => {
    const rs = radios(mountStars({ modelValue: 0 }))
    expect(rs[0].attributes('tabindex')).toBe('0')
    expect(rs.every((r) => r.attributes('aria-checked') === 'false')).toBe(true)
  })

  it('方向键改分：右/左递增递减，Home/End 到端点', async () => {
    const w = mountStars({ modelValue: 3 })
    const rs = radios(w)
    await rs[2].trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([4])
    await rs[2].trigger('keydown', { key: 'ArrowLeft' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([2])
    await rs[2].trigger('keydown', { key: 'Home' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([1])
    await rs[2].trigger('keydown', { key: 'End' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([5])
  })

  it('边界夹住：第 1 颗按左还是 1，第 5 颗按右还是 5（不出现 0 星或 6 星）', async () => {
    const w = mountStars({ modelValue: 1 })
    const rs = radios(w)
    await rs[0].trigger('keydown', { key: 'ArrowLeft' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([1])
    await rs[4].trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([5])
  })

  it('Enter / 空格确认当前星，且不吞掉方向键以外的默认行为', async () => {
    const w = mountStars({ modelValue: 1 })
    await radios(w)[3].trigger('keydown', { key: 'Enter' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([4])
    await radios(w)[1].trigger('keydown', { key: ' ' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([2])
    // 无关按键不该被拦截（比如表单靠 Enter 提交）；方向键则要 preventDefault，
    // 否则页面会跟着滚动。VTU 的 trigger 拿不到事件对象，这里直接派发真 KeyboardEvent。
    const el = radios(w)[0].element
    const plain = new KeyboardEvent('keydown', { key: 'a', bubbles: true, cancelable: true })
    el.dispatchEvent(plain)
    expect(plain.defaultPrevented).toBe(false)
    const arrow = new KeyboardEvent('keydown', {
      key: 'ArrowRight',
      bubbles: true,
      cancelable: true,
    })
    el.dispatchEvent(arrow)
    expect(arrow.defaultPrevented).toBe(true)
  })

  it('鼠标点击照常可用，且点击后 Tab 落点跟到该星', async () => {
    const w = mountStars({ modelValue: 1 })
    await radios(w)[3].trigger('click')
    expect(w.emitted('update:modelValue').at(-1)).toEqual([4])
    await w.setProps({ modelValue: 4 })
    expect(radios(w)[3].attributes('tabindex')).toBe('0')
    expect(radios(w)[0].attributes('tabindex')).toBe('-1')
  })

  it('半星（AI 返回 3.5）：展示保留半星，键盘落点取整且不报错', async () => {
    const w = mountStars({ modelValue: 3.5 })
    expect(w.attributes('aria-label')).toContain('3.5')
    await radios(w)[2].trigger('keydown', { key: 'ArrowRight' })
    expect(w.emitted('update:modelValue').at(-1)).toEqual([4])
    expect(radios(w)[3].attributes('tabindex')).toBe('0')
  })

  it('只读模式：整体是 img，不暴露 radio / tabindex（列表卡片不该被 Tab 逐个穿过）', () => {
    const w = mountStars({ modelValue: 4, readonly: true })
    expect(w.attributes('role')).toBe('img')
    expect(radios(w)).toHaveLength(0)
    expect(w.findAll('[tabindex]')).toHaveLength(0)
    expect(w.text()).not.toContain('星')
  })
})
