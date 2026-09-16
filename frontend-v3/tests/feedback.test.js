/**
 * 第二批组件测试：表单控件续 + 反馈层
 *
 * 重点仍是**契约**（可访问性 / 状态语义 / 焦点管理），不是视觉：
 *  - UiTextarea：标签关联、aria 错误关联、计数
 *  - UiSelect：原生 select（键盘与移动端行为交给浏览器）、placeholder、变更事件
 *  - UiCheck：原生 checkbox 保留（可聚焦可读）、indeterminate 同步、半选视觉
 *  - toast：aria-live 容器、自动消失、最多 4 条、手动关闭
 *  - UiModal：**焦点移入 / Tab 陷阱 / 焦点归还 / Esc / 滚动锁**
 *  - UiEmpty：空态文案与操作插槽；骨架 aria
 */
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import UiCheck from '../src/ui/UiCheck.vue'
import UiEmpty from '../src/ui/UiEmpty.vue'
import UiModal from '../src/ui/UiModal.vue'
import UiSelect from '../src/ui/UiSelect.vue'
import UiTextarea from '../src/ui/UiTextarea.vue'
import { toast } from '../src/ui/toast'

afterEach(() => {
  document.body.innerHTML = ''
  document.body.style.overflow = ''
  vi.useRealTimers()
})

describe('UiTextarea', () => {
  it('标签与控件通过 id 关联', () => {
    const w = mount(UiTextarea, { props: { label: '原文', modelValue: '' } })
    expect(w.find('label').attributes('for')).toBe(w.find('textarea').attributes('id'))
  })

  it('错误走 aria-invalid + aria-describedby', () => {
    const w = mount(UiTextarea, { props: { error: '太长' } })
    const ta = w.find('textarea')
    expect(ta.attributes('aria-invalid')).toBe('true')
    expect(w.find(`#${ta.attributes('aria-describedby')}`).text()).toBe('太长')
  })

  it('showCount 时显示字数，maxLength 存在时显示 x / y', async () => {
    const w = mount(UiTextarea, { props: { showCount: true, maxLength: 80, modelValue: 'abc' } })
    expect(w.text()).toContain('3 / 80')
  })

  it('输入 emit update:modelValue', async () => {
    const w = mount(UiTextarea, { props: { modelValue: '' } })
    await w.find('textarea').setValue('多行\n内容')
    expect(w.emitted('update:modelValue')[0]).toEqual(['多行\n内容'])
  })
})

describe('UiSelect', () => {
  const OPTIONS = [
    { value: 1, label: '数学二' },
    { value: 2, label: '英语二' },
  ]

  it('用原生 select（键盘与移动端行为交给浏览器）', () => {
    const w = mount(UiSelect, { props: { options: OPTIONS } })
    expect(w.find('select').exists()).toBe(true)
    expect(w.findAll('option')).toHaveLength(2)
  })

  it('placeholder 渲染为禁用项', () => {
    const w = mount(UiSelect, { props: { options: OPTIONS, placeholder: '请选择' } })
    const first = w.findAll('option')[0]
    expect(first.text()).toBe('请选择')
    expect(first.attributes('disabled')).toBeDefined()
    expect(w.findAll('option')).toHaveLength(3)
  })

  it('变更 emit 选中值', async () => {
    const w = mount(UiSelect, { props: { options: OPTIONS, modelValue: '' } })
    await w.find('select').setValue('2')
    expect(w.emitted('update:modelValue')[0]).toEqual(['2'])
  })

  it('标签关联 + 错误 aria', () => {
    const w = mount(UiSelect, { props: { options: OPTIONS, label: '科目', error: '必选' } })
    const sel = w.find('select')
    expect(w.find('label').attributes('for')).toBe(sel.attributes('id'))
    expect(sel.attributes('aria-invalid')).toBe('true')
    expect(w.find(`#${sel.attributes('aria-describedby')}`).text()).toBe('必选')
  })
})

describe('UiCheck', () => {
  it('保留原生 checkbox（可聚焦、屏幕阅读器可读），只做视觉接管', () => {
    const w = mount(UiCheck)
    const input = w.find('input[type="checkbox"]')
    expect(input.exists()).toBe(true)
    // 不能用 display:none，否则不可聚焦；这里用 opacity 覆盖
    expect(input.attributes('style')).toBeUndefined()
  })

  it('勾选 emit update:modelValue', async () => {
    const w = mount(UiCheck, { props: { modelValue: false } })
    await w.find('input').setValue(true)
    expect(w.emitted('update:modelValue')[0]).toEqual([true])
  })

  it('indeterminate 时原生属性同步、aria-checked 为 mixed', () => {
    const w = mount(UiCheck, { props: { indeterminate: true } })
    expect(w.find('input').element.indeterminate).toBe(true)
    expect(w.find('input').attributes('aria-checked')).toBe('mixed')
    expect(w.find('.box').classes()).toContain('mixed')
  })

  it('disabled 透传', () => {
    expect(
      mount(UiCheck, { props: { disabled: true } })
        .find('input')
        .attributes('disabled'),
    ).toBeDefined()
  })
})

describe('toast 反馈', () => {
  it('宿主带 aria-live，屏幕阅读器可读', async () => {
    toast.success('已点亮入库')
    const host = document.querySelector('.toast-host')
    expect(host).toBeTruthy()
    expect(host.getAttribute('aria-live')).toBe('polite')
    // toast 走 Vue 异步渲染：宿主是同步创建的，但条目要等一个刷新周期才进 DOM
    await nextTick()
    expect(host.textContent).toContain('已点亮入库')
    toast.clear()
  })

  it('最多同时 4 条（避免刷屏堆满屏幕）', () => {
    for (let i = 0; i < 7; i++) toast.info('第 ' + i + ' 条')
    expect(toast.peek().length).toBeLessThanOrEqual(4)
    toast.clear()
  })

  it('到时自动消失', () => {
    vi.useFakeTimers()
    toast.info('短提示', 1000)
    expect(toast.peek()).toHaveLength(1)
    vi.advanceTimersByTime(1200)
    expect(toast.peek()).toHaveLength(0)
    toast.clear()
  })

  it('可以手动关闭', () => {
    const id = toast.info('可关', 99999)
    toast.dismiss(id)
    expect(toast.peek()).toHaveLength(0)
  })

  it('空文本不产生提示（避免出现空壳）', () => {
    toast.info('')
    expect(toast.peek()).toHaveLength(0)
  })
})

describe('UiModal 焦点与滚动', () => {
  it('打开时锁滚动、aria-modal、标题关联', async () => {
    const w = mount(UiModal, { props: { modelValue: false, title: '详情' } })
    await w.setProps({ modelValue: true })
    await w.vm.$nextTick()
    expect(document.body.style.overflow).toBe('hidden')
    const panel = document.querySelector('[role="dialog"]')
    expect(panel.getAttribute('aria-modal')).toBe('true')
    const titleId = panel.getAttribute('aria-labelledby')
    expect(document.getElementById(titleId).textContent).toBe('详情')
    w.unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('关闭后把焦点还给触发元素（键盘用户不迷路）', async () => {
    const trigger = document.createElement('button')
    trigger.textContent = '打开'
    document.body.appendChild(trigger)
    trigger.focus()

    const w = mount(UiModal, { props: { modelValue: false, title: 'x' } })
    await w.setProps({ modelValue: true })
    await w.vm.$nextTick()
    await w.setProps({ modelValue: false })
    await w.vm.$nextTick()
    expect(document.activeElement).toBe(trigger)
    w.unmount()
  })

  it('Esc 触发关闭（emit update:modelValue false）', async () => {
    const w = mount(UiModal, { props: { modelValue: false, title: 'x' } })
    await w.setProps({ modelValue: true })
    await w.vm.$nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await w.vm.$nextTick()
    const emitted = w.emitted('update:modelValue')
    expect(emitted[emitted.length - 1]).toEqual([false])
    w.unmount()
  })

  it('closeOnEsc=false 时不响应 Esc', async () => {
    const w = mount(UiModal, { props: { modelValue: false, title: 'x', closeOnEsc: false } })
    await w.setProps({ modelValue: true })
    await w.vm.$nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await w.vm.$nextTick()
    expect(w.emitted('update:modelValue')).toBeFalsy()
    w.unmount()
  })

  it('卸载时也会解锁滚动（防止异常路径把页面锁死）', async () => {
    const w = mount(UiModal, { props: { modelValue: false, title: 'x' } })
    await w.setProps({ modelValue: true })
    await w.vm.$nextTick()
    w.unmount()
    expect(document.body.style.overflow).toBe('')
  })

  it('关闭时不渲染弹层（v-if）', () => {
    const w = mount(UiModal, { props: { modelValue: false, title: 'x' } })
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    w.unmount()
  })
})

describe('UiEmpty 空态与骨架', () => {
  it('空态展示标题与提示', () => {
    const w = mount(UiEmpty, { props: { title: '今晚没有待复习', hint: '去录入一道题' } })
    expect(w.text()).toContain('今晚没有待复习')
    expect(w.text()).toContain('去录入一道题')
  })

  it('空态可挂操作按钮（不只是"暂无数据"）', () => {
    const w = mount(UiEmpty, {
      props: { title: '空' },
      slots: { action: '<button>去录入</button>' },
    })
    expect(w.find('button').text()).toBe('去录入')
  })

  it('骨架带 aria 状态与指定行数', () => {
    const w = mount(UiEmpty, { props: { variant: 'skeleton', rows: 3 } })
    expect(w.attributes('role')).toBe('status')
    expect(w.findAll('.sk-line')).toHaveLength(3)
  })

  it('骨架可选缩略图块（形状贴合真实卡片，减少跳版）', () => {
    expect(
      mount(UiEmpty, { props: { variant: 'skeleton', thumb: true } })
        .find('.sk-thumb')
        .exists(),
    ).toBe(true)
    expect(
      mount(UiEmpty, { props: { variant: 'skeleton' } })
        .find('.sk-thumb')
        .exists(),
    ).toBe(false)
  })
})
