/** 轻量 toast 服务：toast.success / error / warning / info */
import { reactive } from 'vue'

let seq = 0
export const toasts = reactive([])

function push(type, message, duration) {
  const id = ++seq
  toasts.push({ id, type, message })
  setTimeout(() => dismiss(id), duration)
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
