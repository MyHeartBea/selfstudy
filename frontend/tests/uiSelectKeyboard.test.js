/**
 * UiSelect 键盘可达性回归。
 *
 * 基件键盘审查（体检第 8 批）发现四件里 UiSelect/UiDropdown 真缺键盘处理、
 * UiCheckbox/UiPagination 是原生元素本就可达（巡检误报）。这里钉 UiSelect：
 * 触发器本是真 button（Tab 可达），缺的是 Esc 关、方向键进菜单并移动焦点、
 * Delete/Backspace 清空 —— 清空按钮嵌在 trigger 按钮内部（嵌套 button 不合法），
 * 键盘用户此前没有任何清空路径。
 */
import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UiSelect from '../src/ui/UiSelect.vue'

const OPTIONS = ['数学', '英语', '政治']

function mountSelect(props = {}) {
  // 必须真挂到 document：detached 元素调用 .focus() 不会移动 activeElement（happy-dom）
  return mount(UiSelect, {
    attachTo: document.body,
    props: { options: OPTIONS, modelValue: null, clearable: true, ...props },
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

async function openAndFocusOption(w, index) {
  await w.find('.select-trigger').trigger('keydown', { key: 'ArrowDown' })
  const option = w.findAll('.select-option')[index]
  option.element.focus()
  return option
}

describe('UiSelect 键盘', () => {
  it('ArrowDown 打开菜单并把焦点放进选中项（无选中则第一项）', async () => {
    const w = mountSelect({ modelValue: '英语' })
    await w.find('.select-trigger').trigger('keydown', { key: 'ArrowDown' })
    expect(w.find('.select-menu').exists()).toBe(true)
    expect(document.activeElement).toBe(w.findAll('.select-option')[1].element)
  })

  it('菜单内 ArrowUp/ArrowDown 在选项间移动焦点，到头不再越界', async () => {
    const w = mountSelect()
    const first = await openAndFocusOption(w, 0)
    await first.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(w.findAll('.select-option')[1].element)
    await w.findAll('.select-option')[2].element.focus()
    await w.findAll('.select-option')[2].trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(w.findAll('.select-option')[2].element)
  })

  it('Esc 关闭菜单并把焦点还给触发器', async () => {
    const w = mountSelect()
    await w.find('.select-trigger').trigger('click')
    await w.find('.select-menu').trigger('keydown', { key: 'Escape' })
    expect(w.find('.select-menu').exists()).toBe(false)
    expect(document.activeElement).toBe(w.find('.select-trigger').element)
  })

  it('Delete/Backspace 清空选中值（键盘唯一的清空路径）', async () => {
    const w = mountSelect({ modelValue: '数学' })
    await w.find('.select-trigger').trigger('keydown', { key: 'Delete' })
    expect(w.emitted('update:modelValue')[0]).toEqual([null])
    expect(w.emitted('change')[0]).toEqual([null])
  })

  it('未选中时 Delete 不误发清空事件', async () => {
    const w = mountSelect({ modelValue: null })
    await w.find('.select-trigger').trigger('keydown', { key: 'Delete' })
    expect(w.emitted('update:modelValue')).toBeFalsy()
  })
})
