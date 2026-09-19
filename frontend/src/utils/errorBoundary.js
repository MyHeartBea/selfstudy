/**
 * 全局错误边界：Vue 组件渲染抛错 / 未捕获异常时，给用户一个能看清并自救的界面。
 *
 * 为什么必须有：改之前全站没有 `app.config.errorHandler` 也没有 `window.onerror`，
 * 任何一个组件在 setup/render 里抛错都会让 `#app` 停在半渲染状态（实测就是白屏），
 * 而启动屏的收起逻辑挂在挂载成功之后 —— 于是白屏上还可能压着一层遮罩，
 * 用户只能手动刷新，且刷新前什么信息都留不下。
 *
 * 只兜"渲染期与运行期"的意外，不改业务错误处理：接口 4xx/5xx 仍走 axios 拦截器的 toast。
 */

let shown = false

function dismissSplash() {
  const splash = document.getElementById('splash')
  if (splash) splash.remove()
  document.body.classList.add('app-ready', 'ready')
}

/**
 * 显示致命错误面板。用原生 DOM 而不是 Vue 组件：
 * 走到这里时应用本身可能已经渲染不出来，任何依赖运行时都不可信。
 */
export function showFatal(detail) {
  if (shown) return
  shown = true
  dismissSplash()
  if (document.getElementById('km-fatal')) return

  const text = String(detail?.message || detail || '未知错误').slice(0, 300)
  const wrap = document.createElement('div')
  wrap.id = 'km-fatal'
  wrap.setAttribute('role', 'alert')
  wrap.style.cssText = [
    'position:fixed',
    'inset:auto 16px 16px 16px',
    'max-width:520px',
    'margin:0 auto',
    'z-index:9999',
    'padding:14px 16px',
    'background:var(--surface,#fff)',
    'color:var(--ink,#222)',
    'border:1px solid var(--accent,#b3261e)',
    'border-radius:var(--r-md,10px)',
    'box-shadow:var(--shadow-3,0 12px 32px rgba(0,0,0,.18))',
    'font-size:14px',
    'line-height:1.6',
  ].join(';')

  const title = document.createElement('strong')
  title.textContent = '页面出错了'
  const body = document.createElement('div')
  body.textContent = text
  body.style.cssText = 'margin:6px 0 10px;color:var(--ink-2,#555)'

  const reload = document.createElement('button')
  reload.textContent = '重新加载'
  reload.style.cssText = 'margin-right:8px;padding:6px 14px;cursor:pointer'
  reload.addEventListener('click', () => window.location.reload())

  const home = document.createElement('button')
  home.textContent = '回首页'
  home.style.cssText = 'padding:6px 14px;cursor:pointer'
  home.addEventListener('click', () => {
    window.location.hash = ''
    window.location.pathname = '/'
  })

  // 有些错误只影响一个分支（页面其余部分照常），所以留一条"知道了"；
  // 但闸门不重置 —— 同一次会话里不再重复弹窗砸脸。
  const dismiss = document.createElement('button')
  dismiss.textContent = '知道了'
  dismiss.style.cssText =
    'margin-left:8px;padding:6px 14px;cursor:pointer;background:transparent;border:none;color:var(--ink-3,#888)'
  dismiss.addEventListener('click', () => wrap.remove())

  wrap.append(title, body, reload, home, dismiss)
  document.body.appendChild(wrap)
}

/** 安装到 Vue 应用：渲染 / 生命周期 / watcher 里抛出的错误都汇到这里。 */
export function installErrorBoundary(app) {
  app.config.errorHandler = (err, _instance, info) => {
    console.error('[km] 未捕获的组件错误：', info, err)
    showFatal(err)
  }
}

/** 兜住 Vue 之外的异常（事件回调里的抛错、Promise 未处理拒绝）。 */
export function installWindowGuards() {
  window.addEventListener('error', (event) => {
    // 资源加载失败（图片/字体 404）的 error 事件没有 message，不该当成致命错误
    if (!event.error) return
    console.error('[km] 未捕获异常：', event.error)
    showFatal(event.error)
  })
  window.addEventListener('unhandledrejection', (event) => {
    // 接口 4xx/5xx 已由 axios 拦截器弹过 toast，这里只留一行日志便于排查，
    // 不再重复弹窗（那会变成"一个网络抖动两块砖"）。
    console.error('[km] 未处理的 Promise 拒绝：', event.reason)
  })
}

/** 测试用：重置只显示一次的闸门。 */
export function __resetFatalForTest() {
  shown = false
  document.getElementById('km-fatal')?.remove()
}
