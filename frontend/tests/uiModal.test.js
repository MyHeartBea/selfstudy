/**
 * UiModal 的焦点圈与滚动锁回归。
 *
 * 两件事都是"叠层"才暴露的问题：
 *  1. 滚动锁必须是全站计数 —— 各层各写 `body.style.overflow=''` 的话，
 *     关掉最上面那层会顺手把下面还开着的层一起解锁（背景又能滚了）。
 *  2. 焦点要圈在面板里并在关闭后还给触发元素，否则 Tab 会跑到被遮住的页面上。
 *
 * 弹窗是 Teleport 到 document.body 的，断言一律查 document。
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UiModal from '../src/ui/UiModal.vue'

function mountModal(title) {
  return mount(UiModal, { props: { modelValue: true, title }, attachTo: document.body })
}

beforeEach(() => {
  document.body.innerHTML = ''
  document.body.style.overflow = ''
})

describe('UiModal 滚动锁', () => {
  it('关内层不解外层的锁，全关完才还原', async () => {
    const outer = mountModal('外层')
    const inner = mountModal('内层')
    await inner.vm.$nextTick()
    expect(document.body.style.overflow).toBe('hidden')

    await inner.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('hidden')

    await outer.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('')
  })

  it('卸载时仍开着的弹窗会把锁带走（不漏计）', async () => {
    const outer = mountModal('外层')
    const inner = mountModal('内层')
    await inner.vm.$nextTick()
    inner.unmount()
    expect(document.body.style.overflow).toBe('hidden')
    outer.unmount()
    expect(document.body.style.overflow).toBe('')
  })
})

describe('UiModal 焦点', () => {
  it('以 modelValue=true 挂载也会抢焦点（不只监听 false→true）', async () => {
    const modal = mountModal('直接挂载')
    await modal.vm.$nextTick()
    const panel = document.querySelector('.modal-panel')
    expect(document.activeElement).toBe(panel)
    expect(panel.getAttribute('aria-labelledby')).toBe(document.querySelector('.modal-title').id)
  })

  it('关闭后焦点回到触发元素', async () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    const modal = mount(UiModal, {
      props: { modelValue: false, title: '回到我' },
      attachTo: document.body,
    })
    await modal.setProps({ modelValue: true })
    await modal.vm.$nextTick()
    expect(document.activeElement).toBe(document.querySelector('.modal-panel'))

    await modal.setProps({ modelValue: false })
    expect(document.activeElement).toBe(trigger)
  })
})
