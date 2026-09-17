/**
 * 悬停复合特效的指针追踪（km-live.js）
 * ===========================================================================
 * 配套 styles/km-live.css 的 7 层悬停。这里只做 JS 才能做的两件事：
 *   ① 3D 倾斜：按指针在元素内的相对位置算出 --rx/--ry（CSS 无法从指针位置算角度）
 *   ② 光晕位置：写 --mx/--my 给 CSS 的径向渐变用
 *
 * 为什么不在每个组件里写：v2 有 8 个列表页，逐页写 mousemove 会重复且容易漏。
 * 这里统一用**事件委托**（挂在 document 上）：
 *   · 只有 pointerType 为 mouse 且命中 .km-live 时才计算
 *   · 用 rAF 节流：一帧只处理一次（mousemove 触发频率远高于帧率）
 *
 * 边界（都踩过）：
 *   · 触屏/粗指针直接跳过（倾斜会让点击目标漂移）
 *   · 离开时把变量清空，否则下次进入会从旧角度开始
 *   · 不写内联 transform，只写 CSS 变量 —— 避免与其他 transform 动画互相覆盖
 */

const MAX_DEG = 8 // 倾斜上限（参考稿用 8/10，这里统一 8，收敛一点更耐看）
const MAX_RY = 10

let raf = 0
let pending = null
let bound = false

function allowed() {
  if (typeof window === 'undefined') return false
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  return matchMedia('(hover: hover) and (pointer: fine)').matches
}

function apply(el, x, y) {
  const r = el.getBoundingClientRect()
  if (!r.width || !r.height) return
  const px = (x - r.left) / r.width
  const py = (y - r.top) / r.height
  // y 轴反向：鼠标在上方时卡片"向后仰"
  el.style.setProperty('--rx', `${((0.5 - py) * MAX_DEG).toFixed(2)}deg`)
  el.style.setProperty('--ry', `${((px - 0.5) * MAX_RY).toFixed(2)}deg`)
  el.style.setProperty('--mx', `${(px * 100).toFixed(1)}%`)
  el.style.setProperty('--my', `${(py * 100).toFixed(1)}%`)
}

function reset(el) {
  if (!el) return
  el.style.removeProperty('--rx')
  el.style.removeProperty('--ry')
  el.style.removeProperty('--mx')
  el.style.removeProperty('--my')
}

export function startLiveHover() {
  if (bound || typeof document === 'undefined') return () => {}
  if (!allowed()) return () => {}
  bound = true

  const onMove = (e) => {
    if (e.pointerType && e.pointerType !== 'mouse') return
    const el = e.target?.closest?.('.km-live')
    if (!el) return
    pending = { el, x: e.clientX, y: e.clientY }
    if (raf) return
    raf = requestAnimationFrame(() => {
      raf = 0
      if (pending) {
        apply(pending.el, pending.x, pending.y)
        pending = null
      }
    })
  }

  const onOut = (e) => {
    const el = e.target?.closest?.('.km-live')
    if (!el) return
    // 只有真正离开该元素才重置（子元素间移动会冒泡出 out 事件）
    const to = e.relatedTarget
    if (to && el.contains(to)) return
    reset(el)
  }

  document.addEventListener('pointermove', onMove, { passive: true })
  document.addEventListener('pointerout', onOut, { passive: true })

  return () => {
    document.removeEventListener('pointermove', onMove)
    document.removeEventListener('pointerout', onOut)
    cancelAnimationFrame(raf)
    raf = 0
    bound = false
  }
}

export function stopLiveHover() {
  bound = false
}
