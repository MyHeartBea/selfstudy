/**
 * 组件层测试（happy-dom）
 *
 * 重点不是"长得对不对"（那由真浏览器像素校验负责），而是**契约**：
 *   - InkCard：整块可点是否真的在卡片自身上（v2 事故的正面回归）；内部控件是否真的 stop
 *   - UiField：标签是否与控件关联；错误是否用 aria 关联而不只是变色；禁用是否真的禁
 *   - UiButton：loading 是否禁用 + aria-busy；type 默认是否为 button（防止表单误提交）
 *   - InkDot / StarRow：无障碍是否给出可读的数值文本
 *   - UiTag：tone 是否落到类名（语义色靠它）
 */
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InkCard from '../src/ui/InkCard.vue'
import InkDot from '../src/ui/InkDot.vue'
import StarRow from '../src/ui/StarRow.vue'
import UiButton from '../src/ui/UiButton.vue'
import UiField from '../src/ui/UiField.vue'
import UiTag from '../src/ui/UiTag.vue'

describe('InkCard 整块可点', () => {
  it('默认渲染为 button，点卡片任意位置都触发 select', async () => {
    const w = mount(InkCard, { slots: { default: '<h3>标题</h3><p>正文摘要</p>' } })
    expect(w.element.tagName).toBe('BUTTON')
    expect(w.attributes('type')).toBe('button')
    await w.find('h3').trigger('click')
    await w.find('p').trigger('click')
    expect(w.emitted('select')).toHaveLength(2)
  })

  it('键盘可用：Enter 与 Space 都能触发（Space 需阻止默认滚动）', async () => {
    const w = mount(InkCard, { slots: { default: 'x' } })
    await w.trigger('keydown.enter')
    await w.trigger('keydown.space')
    expect(w.emitted('select')).toHaveLength(2)
  })

  it('非交互模式渲染为 article，且不响应点击（内部放控件时用）', async () => {
    const w = mount(InkCard, { props: { interactive: false }, slots: { default: 'x' } })
    expect(w.element.tagName).toBe('ARTICLE')
    await w.trigger('click')
    expect(w.emitted('select')).toBeFalsy()
  })

  it('flagged 会加标记类（反复错的标志层语义）', () => {
    const w = mount(InkCard, { props: { flagged: true } })
    expect(w.classes()).toContain('flagged')
  })

  it('spine 通过 CSS 变量传入，不写进内联样式表以外的地方', () => {
    const w = mount(InkCard, { props: { spine: 'rgb(255, 90, 60)' } })
    expect(w.attributes('style')).toContain('--spine')
  })
})

describe('UiField 表单契约', () => {
  it('标签与控件通过 id 正确关联（点标签能聚焦）', () => {
    const w = mount(UiField, { props: { label: '题干', modelValue: '' } })
    const id = w.find('input').attributes('id')
    expect(id).toBeTruthy()
    expect(w.find('label').attributes('for')).toBe(id)
  })

  it('错误用 aria-invalid + aria-describedby 关联提示，不只是变红', () => {
    const w = mount(UiField, { props: { error: '必填' } })
    const input = w.find('input')
    expect(input.attributes('aria-invalid')).toBe('true')
    const desc = input.attributes('aria-describedby')
    expect(desc).toBeTruthy()
    expect(w.find(`#${desc}`).text()).toBe('必填')
  })

  it('hint 与 error 互斥：有错误时不显示 hint', () => {
    const w = mount(UiField, { props: { hint: '提示', error: '错误' } })
    expect(w.text()).toContain('错误')
    expect(w.text()).not.toContain('提示')
  })

  it('disabled 会透传到原生控件', () => {
    const w = mount(UiField, { props: { disabled: true } })
    expect(w.find('input').attributes('disabled')).toBeDefined()
  })

  it('输入会 emit update:modelValue（v-model 可用）', async () => {
    const w = mount(UiField, { props: { modelValue: '' } })
    await w.find('input').setValue('泰勒')
    expect(w.emitted('update:modelValue')[0]).toEqual(['泰勒'])
  })
})

describe('UiButton 状态与安全默认', () => {
  it('type 默认是 button（避免放进表单时意外提交）', () => {
    expect(mount(UiButton).attributes('type')).toBe('button')
  })

  it('loading 时禁用并标记 aria-busy', () => {
    const w = mount(UiButton, { props: { loading: true } })
    expect(w.attributes('disabled')).toBeDefined()
    expect(w.attributes('aria-busy')).toBe('true')
  })

  it('disabled 时不触发点击', async () => {
    const w = mount(UiButton, { props: { disabled: true } })
    await w.trigger('click')
    expect(w.element.disabled).toBe(true)
  })

  it('变体与尺寸落到类名（语义色靠类名切换）', () => {
    const w = mount(UiButton, { props: { variant: 'solid', size: 'lg' } })
    expect(w.classes()).toContain('v-solid')
    expect(w.classes()).toContain('s-lg')
  })
})

describe('InkDot 掌握度', () => {
  it('按档位点亮对应数量的圆点', () => {
    const w = mount(InkDot, { props: { value: 3, max: 5 } })
    expect(w.findAll('i')).toHaveLength(5)
    expect(w.findAll('i.on')).toHaveLength(3)
  })

  it('超出范围会被夹紧（不抛异常）', () => {
    expect(mount(InkDot, { props: { value: 99 } }).findAll('i.on')).toHaveLength(5)
    expect(mount(InkDot, { props: { value: -3 } }).findAll('i.on')).toHaveLength(0)
  })

  it('无障碍给出可读数值', () => {
    const w = mount(InkDot, { props: { value: 2, max: 5, label: '掌握度' } })
    expect(w.attributes('role')).toBe('img')
    expect(w.attributes('aria-label')).toBe('掌握度 2 / 5')
  })
})

describe('StarRow 星等', () => {
  it('用 SVG 星形而不是 Unicode 星号（全站禁用字符图标）', () => {
    const w = mount(StarRow, { props: { value: 4, max: 7 } })
    expect(w.findAll('svg.star')).toHaveLength(7)
    expect(w.findAll('svg.star.on')).toHaveLength(4)
    expect(w.text()).toBe('') // 不含任何文字/字符图标
  })

  it('无障碍给出可读数值', () => {
    const w = mount(StarRow, { props: { value: 5, max: 7, label: '复习遍数' } })
    expect(w.attributes('aria-label')).toBe('复习遍数 5 / 7')
  })
})

describe('UiTag 语义色', () => {
  it('tone 与 size 落到类名', () => {
    const w = mount(UiTag, { props: { tone: 'vein', size: 'sm' } })
    expect(w.classes()).toContain('t-vein')
    expect(w.classes()).toContain('s-sm')
  })

  it('dot 可选，默认不渲染圆点', () => {
    expect(mount(UiTag).find('i.dot').exists()).toBe(false)
    expect(
      mount(UiTag, { props: { dot: true } })
        .find('i.dot')
        .exists(),
    ).toBe(true)
  })
})
