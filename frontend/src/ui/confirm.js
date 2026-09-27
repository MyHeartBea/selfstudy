/**
 * 确认 / 输入弹窗服务（Promise 风格），由 ConfirmHost 组件渲染：
 *   const ok = await confirmDialog({ title, message, danger: true })
 *   const year = await confirmDialog({ title, message, input: { placeholder, value, pattern, error } })
 */
import { reactive } from 'vue'

export const confirmState = reactive({
  open: false,
  title: '',
  message: '',
  danger: false,
  confirmText: '确定',
  input: null,
  inputValue: '',
  error: '',
})

let resolver = null

function finish(result) {
  confirmState.open = false
  if (resolver) {
    resolver(result)
    resolver = null
  }
}

export function confirmCancel() {
  finish(null)
}

export function confirmOk() {
  const state = confirmState
  if (state.input) {
    const value = String(state.inputValue || '').trim()
    if (state.input.pattern && !state.input.pattern.test(value)) {
      state.error = state.input.error || '输入格式不正确'
      return
    }
    finish(value)
  } else {
    finish(true)
  }
}

export function confirmDialog(options = {}) {
  // 旧弹窗还没人应答就来了新的：把旧的按"取消"落地——否则第一个 await
  // 永远挂起，提交流程会卡死在一个看不见的弹窗上
  if (resolver) {
    resolver(null)
    resolver = null
  }
  confirmState.title = options.title || '确认操作'
  confirmState.message = options.message || ''
  confirmState.danger = options.danger === true
  confirmState.confirmText = options.confirmText || '确定'
  confirmState.input = options.input || null
  confirmState.inputValue = confirmState.input?.value ? String(confirmState.input.value) : ''
  confirmState.error = ''
  confirmState.open = true
  return new Promise((resolve) => {
    resolver = resolve
  })
}
