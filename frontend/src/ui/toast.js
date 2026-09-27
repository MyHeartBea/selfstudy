/** 轻量 toast 服务：toast.success / error / warning / info */
import { reactive } from 'vue'

let seq = 0
export const toasts = reactive([])

// 同文案合并 + 数量上限：批量操作时拦截器连发 toast 会叠一摞挡住页面
const MAX_TOASTS = 5

function push(type, message, duration) {
  const dup = toasts.find((t) => t.type === type && t.message === message)
  if (dup) {
    // 同文案只刷新一次存活时间，不重复叠条
    clearTimeout(dup._timer)
    dup._timer = setTimeout(() => dismiss(dup.id), duration)
    return
  }
  while (toasts.length >= MAX_TOASTS) toasts.shift()
  const id = ++seq
  const item = { id, type, message }
  item._timer = setTimeout(() => dismiss(id), duration)
  toasts.push(item)
}

export function dismiss(id) {
  const index = toasts.findIndex((item) => item.id === id)
  if (index !== -1) toasts.splice(index, 1)
}

export const toast = {
  success: (msg, duration = 2600) => push('success', msg, duration),
  error: (msg, duration = 4200) => push('error', msg, duration),
  warning: (msg, duration = 3400) => push('warning', msg, duration),
  info: (msg, duration = 3000) => push('info', msg, duration),
}
