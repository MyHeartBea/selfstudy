/**
 * v-reveal 指令：元素进入视口时交错浮现。
 * 用法：v-reveal 或 v-reveal="80"（延迟 ms）
 */
const observer =
  typeof IntersectionObserver !== 'undefined'
    ? new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              const el = entry.target
              const delay = Number(el.dataset.revealDelay || 0)
              el.style.transitionDelay = `${delay}ms`
              el.classList.add('reveal-in')
              // 交错延迟只在入场时生效：transition 结束后清掉 inline delay，
              // 否则元素后续的 hover 等过渡全被拖着这几十毫秒（实测 hover 变钝）
              const clearDelay = () => {
                el.style.transitionDelay = ''
              }
              el.addEventListener('transitionend', clearDelay, { once: true })
              setTimeout(clearDelay, delay + 800) // 兜底：transitionend 被吞也不残留
              observer.unobserve(el)
            }
          }
        },
        { threshold: 0.08, rootMargin: '0px 0px -20px 0px' },
      )
    : null

export const reveal = {
  mounted(el, binding) {
    if (!observer) return
    el.classList.add('reveal-pending')
    if (binding.value) el.dataset.revealDelay = String(binding.value)
    observer.observe(el)
  },
  unmounted(el) {
    if (observer) observer.unobserve(el)
  },
}
