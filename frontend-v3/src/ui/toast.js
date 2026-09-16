/*
 * Toast —— 轻量反馈（星尘提示）
 * ---------------------------------------------------------------------------
 * 设计约束（来自项目要求与过往踩坑）：
 *  - **不阻塞操作**：出现在视口右下（桌面）或底部（移动），不居中遮挡，不锁滚动
 *  - **可访问**：容器 role="status" + aria-live="polite"，屏幕阅读器会读；错误类用 assertive
 *  - **不自动播放声音**、不申请权限
 *  - 只改 transform / opacity；多条堆叠按 index 错位
 *
 * 用法（命令式，与 v2 的 toast 调用方式一致，便于迁移）：
 *   import { toast } from '../ui/toast'
 *   toast.success('已点亮入库')
 *   toast.error('入库失败')
 *   toast.info('今晚还有 38 题')
 */
import { createApp, h, reactive } from 'vue'

const state = reactive({ items: [] })
let seq = 0
let host = null

/** 单条提示的生命周期：默认 2.8s，可点关闭 */
function push(kind, text, duration = 2800) {
  if (!text) return
  const id = ++seq
  state.items.push({ id, kind, text })
  // 最多同时显示 4 条，超出的挤掉最早的（避免刷屏堆满屏幕）
  if (state.items.length > 4) state.items.shift()
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

function dismiss(id) {
  const i = state.items.findIndex((t) => t.id === id)
  if (i >= 0) state.items.splice(i, 1)
}

function ensureHost() {
  if (host || typeof document === 'undefined') return
  host = document.createElement('div')
  host.className = 'toast-host'
  host.setAttribute('role', 'status')
  host.setAttribute('aria-live', 'polite')
  host.setAttribute('aria-atomic', 'false')
  document.body.appendChild(host)
  createApp({
    setup() {
      return () =>
        h(
          'div',
          { class: 'toast-stack' },
          state.items.map((t) =>
            h(
              'div',
              {
                key: t.id,
                class: ['toast', `k-${t.kind}`],
                onClick: () => dismiss(t.id),
              },
              [
                h('span', { class: 'dot', 'aria-hidden': 'true' }),
                h('span', { class: 'txt' }, t.text),
              ],
            ),
          ),
        )
    },
  }).mount(host)
}

export const toast = {
  success: (text, d) => {
    ensureHost()
    return push('success', text, d)
  },
  error: (text, d) => {
    ensureHost()
    return push('error', text, d ?? 4200)
  },
  info: (text, d) => {
    ensureHost()
    return push('info', text, d)
  },
  dismiss,
  /** 测试用：清空全部 */
  clear: () => state.items.splice(0, state.items.length),
  /** 测试用：读取当前条目 */
  peek: () => state.items.slice(),
}
