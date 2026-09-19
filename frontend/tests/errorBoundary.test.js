/**
 * 全局错误边界（utils/errorBoundary.js）：出致命错时必须给用户一个看得懂、能自救的面板，
 * 而不是让 #app 停在半渲染状态、上面还压着一层永远不散的启动屏遮罩。
 *
 * 面板用原生 DOM 建，所以这里也直接用 document / window 断言，不经 Vue 测试工具。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  installErrorBoundary,
  installWindowGuards,
  showFatal,
  __resetFatalForTest as resetFatal,
} from '../src/utils/errorBoundary'

function panel() {
  return document.getElementById('km-fatal')
}

describe('errorBoundary 全局错误边界', () => {
  beforeEach(() => {
    resetFatal()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('showFatal：渲染可访问的告警面板，带上错误信息与三个自救按钮', () => {
    showFatal(new Error('组件炸了'))
    const el = panel()
    expect(el).not.toBeNull()
    expect(el.getAttribute('role')).toBe('alert')
    expect(el.textContent).toContain('页面出错了')
    expect(el.textContent).toContain('组件炸了')
    const labels = [...el.querySelectorAll('button')].map((b) => b.textContent)
    expect(labels).toEqual(['重新加载', '回首页', '知道了'])
  })

  it('顺手收掉启动屏：否则错误面板会被遮罩压在下面', () => {
    const splash = document.createElement('div')
    splash.id = 'splash'
    document.body.appendChild(splash)
    showFatal('boom')
    expect(document.getElementById('splash')).toBeNull()
    expect(document.body.classList.contains('app-ready')).toBe(true)
  })

  it('只弹一次：后续错误不覆盖第一条信息，也不追加面板', () => {
    showFatal(new Error('第一个错误'))
    showFatal(new Error('第二个错误'))
    expect(document.querySelectorAll('#km-fatal').length).toBe(1)
    expect(panel().textContent).toContain('第一个错误')
    expect(panel().textContent).not.toContain('第二个错误')
  })

  it('「知道了」可以关掉面板（错误只影响单个分支时不该砸脸）', () => {
    showFatal('只是某个角落坏了')
    const buttons = panel().querySelectorAll('button')
    buttons[buttons.length - 1].click()
    expect(panel()).toBeNull()
  })

  it('超长堆栈被截断，不把面板撑成一屏乱码', () => {
    showFatal(new Error('x'.repeat(1000)))
    expect(panel().textContent).not.toContain('x'.repeat(400))
  })

  it('installErrorBoundary：装到 app.config.errorHandler 上并转成面板', () => {
    const app = { config: {} }
    installErrorBoundary(app)
    expect(typeof app.config.errorHandler).toBe('function')
    app.config.errorHandler(new Error('render 抛错'), null, 'render')
    expect(panel().textContent).toContain('render 抛错')
    expect(console.error).toHaveBeenCalled()
  })

  it('installWindowGuards：真异常上屏，资源 404（无 error 对象）保持静默', () => {
    installWindowGuards()
    // 图片 / 字体加载失败的 error 事件没有 event.error，当成致命错误会让全站满屏弹窗
    window.dispatchEvent(new Event('error'))
    expect(panel()).toBeNull()

    resetFatal()
    const evt = new ErrorEvent('error', { error: new Error('事件回调里抛错') })
    window.dispatchEvent(evt)
    expect(panel().textContent).toContain('事件回调里抛错')
  })

  it('unhandledrejection：只记录日志，不弹面板（axios 已弹过 toast）', () => {
    installWindowGuards()
    // happy-dom 没有 PromiseRejectionEvent 构造器，用普通 Event 挂 reason 即可（处理器只读它）
    const evt = new Event('unhandledrejection')
    evt.reason = new Error('接口 500')
    window.dispatchEvent(evt)
    expect(panel()).toBeNull()
    expect(console.error).toHaveBeenCalled()
  })
})
