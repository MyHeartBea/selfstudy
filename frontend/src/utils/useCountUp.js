/** 数字滚动动画：从 0（或指定值）缓动到目标值。 */
import { onBeforeUnmount, watch } from 'vue'
import { ref } from 'vue'

/**
 * @param {import('vue').Ref<number|string>} source 响应式目标值
 * @param {object} [options]
 * @param {number} [options.duration=900] 动画时长 ms
 * @param {(v:number)=>string} [options.format] 格式化（如加 % 或小数）
 */
export function useCountUp(source, options = {}) {
  const duration = options.duration || 900
  const format = options.format || ((v) => String(v))
  const display = ref(format(toNumber(source.value)))
  let rafId = null

  function toNumber(value) {
    const n = parseFloat(value)
    return Number.isFinite(n) ? n : 0
  }

  function animateTo(target) {
    if (rafId) cancelAnimationFrame(rafId)
    const from = parseFloat(display.value) || 0
    const start = performance.now()
    if (target === from) {
      display.value = format(target)
      return
    }
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration)
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3)
      const value = from + (target - from) * eased
      display.value = format(
        Number.isInteger(target) ? Math.round(value) : Math.round(value * 10) / 10,
      )
      if (t < 1) rafId = requestAnimationFrame(step)
      else display.value = format(target)
    }
    rafId = requestAnimationFrame(step)
  }

  watch(
    () => source.value,
    (value) => animateTo(toNumber(value)),
    { immediate: true },
  )

  onBeforeUnmount(() => {
    if (rafId) cancelAnimationFrame(rafId)
  })

  return display
}
