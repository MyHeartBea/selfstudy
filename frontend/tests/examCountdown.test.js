/**
 * 全局考研倒计时印（ui/ExamCountdown.vue）：三档语气 + 两种形态 + 该隐藏时必须隐藏。
 *
 * 它是外壳层元素（每条路由都在），所以数据缺失/已考完时必须整块不渲染，
 * 否则页面上会挂一个 "距考研 null 天" 的尴尬印章。
 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import ExamCountdown from '../src/ui/ExamCountdown.vue'

function mountCd(props) {
  return mount(ExamCountdown, {
    props: { days: 91, date: '2026-12-19', passed: false, ...props },
  })
}

describe('ExamCountdown 全局倒计时印', () => {
  it('常态：显示天数与日期，档位 calm', () => {
    const w = mountCd({})
    expect(w.element.nodeType).toBe(1) // 对照：正常渲染时根节点是真元素（不是注释）
    expect(w.classes()).toContain('tier-calm')
    expect(w.text()).toContain('距考研')
    expect(w.text()).toContain('91')
    expect(w.text()).toContain('12 · 19')
    expect(w.attributes('role')).toBe('status')
    expect(w.attributes('aria-label')).toContain('初试日期 2026-12-19')
  })

  it('三档语气：<=30 紧迫、<=7 冲刺且文案换成「最后冲刺」', () => {
    expect(mountCd({ days: 20 }).classes()).toContain('tier-hot')
    const final = mountCd({ days: 5 })
    expect(final.classes()).toContain('tier-final')
    expect(final.text()).toContain('最后冲刺')
  })

  it('日期非法（days=null）或初试已过时整块不渲染', () => {
    // 根节点带 v-if：不渲染时 Vue 留的是注释节点（nodeType 8）。
    // 不用 find('.exam-cd') —— VTU 的 find 只查后代，根元素自己查不到，否定断言会假通过。
    expect(mountCd({ days: null }).element.nodeType).toBe(8)
    expect(mountCd({ days: 0, passed: true }).element.nodeType).toBe(8)
  })

  it('窄屏 compact：不显示日期，只留数字', () => {
    const w = mountCd({ compact: true })
    expect(w.classes()).toContain('compact')
    expect(w.find('.cd-date').exists()).toBe(false)
    expect(w.text()).toContain('91')
  })
})
