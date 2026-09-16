/**
 * 动效原语（Motion Primitives）—— 夜航星图的全部动作词汇
 * ---------------------------------------------------------------------------
 * 设计原则：**每条原语都必须能回答"这一步对应哪个物理动作"**。
 * 不允许为了好看而存在的动效。全部只作用于 transform / opacity / filter，
 * 不读写布局属性（不触发 layout thrash）。
 *
 * 六条原语（与设计令牌里的三条曲线一一对应）：
 *   drift    漂移   缓慢、匀速、无始无终 —— 星云、视差、背景呼吸（--e-drift）
 *   settle   沉降   从模糊到位、由远及近 —— 内容入场、章节揭示（--e-settle）
 *   flare    红移   过冲回弹、一锤定音 —— 确认、错误、落定（--e-flare）
 *   trace    描绘   从左至右写出 —— 数据曲线、进度（SVG stroke-dashoffset）
 *   scan     扫描   穿越式掠过 —— 等待上游/解析中（说明"在处理"，不编造百分比）
 *   focus    聚焦   同心圈收紧 —— 键盘焦点、命中定位
 *
 * 全部提供 prefers-reduced-motion 降级：**瞬时到位、信息不丢**，
 * 而不是"关掉动画导致内容不出现"。
 *
 * 用法：
 *   import { revealOnScroll, stagger, magnetic, traceOnScroll, prefersReduced } from '../design/motion'
 *   const stop = revealOnScroll(el, { delay: 80 })
 *   onBeforeUnmount(stop)
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

/** 是否要求减少动效（响应式：用户改系统设置也能跟着变） */
export function prefersReduced() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** 曲线常量与 CSS 变量保持一致（需要 JS 侧计算时用） */
export const CURVE = {
  drift: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  settle: 'cubic-bezier(0.19, 1, 0.22, 1)',
  flare: 'cubic-bezier(0.34, 1.42, 0.4, 1)',
}

/**
 * 是否真的是 DOM 元素。
 *
 * 为什么必须要有这个守卫（实测踩过）：把 `ref` 传进原语时，若拿到的是**组件实例代理**
 * （ref 绑在自定义组件而非原生元素上），它是普通对象、没有 addEventListener，
 * 直接调用会抛 `el.addEventListener is not a function`。
 * 而这个异常发生在 onMounted 内部，**会让同一钩子里后面的原语全部不执行** ——
 * 表现是"元素永远不出现"（reveal 不生效）并且加载页卡住，排查成本极高。
 * 所以所有原语入口一律先判定；不满足就静默跳过并返回空清理函数。
 */
export function isElement(el) {
  return (
    !!el && typeof el === 'object' && typeof el.addEventListener === 'function' && el.nodeType === 1
  )
}

/* ── 1. settle：滚动进入视口时沉降到位 ─────────────────────────────────── */
/**
 * 元素进入视口后加上 .in 类（由 CSS 负责过渡），只触发一次。
 * @returns 清理函数
 */
export function revealOnScroll(
  el,
  { threshold = 0.14, rootMargin = '0px 0px -6% 0px', once = true } = {},
) {
  if (!isElement(el)) return () => {}
  if (prefersReduced() || !('IntersectionObserver' in window)) {
    el.classList.add('in')
    return () => {}
  }
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return
        entry.target.classList.add('in')
        if (once) io.unobserve(entry.target)
      })
    },
    { threshold, rootMargin },
  )
  io.observe(el)
  return () => io.disconnect()
}

/** 批量观察 + 错峰延迟（同一组元素依次入场，而不是一起冒出来） */
export function revealAll(els, { stagger: staggerMs = 70, ...opts } = {}) {
  const list = [...(els || [])].filter(isElement)
  const stops = list.map((el, i) => {
    el.style.transitionDelay = `${i * staggerMs}ms`
    return revealOnScroll(el, opts)
  })
  return () => stops.forEach((fn) => fn())
}

/* ── 2. drift：指针视差（分层景深） ────────────────────────────────────── */
/**
 * 让元素随指针轻微位移，形成前景/背景分层。depth 越大越"近"。
 * 用 rAF + lerp 驱动，只写 transform。
 */
export function parallax(el, { depth = 12, ease = 0.06 } = {}) {
  if (!isElement(el) || prefersReduced()) return () => {}
  if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return () => {}

  let tx = 0
  let ty = 0
  let cx = 0
  let cy = 0
  let raf = 0

  const onMove = (e) => {
    tx = (e.clientX / window.innerWidth - 0.5) * depth * 2
    ty = (e.clientY / window.innerHeight - 0.5) * depth * 2
  }
  const loop = () => {
    cx += (tx - cx) * ease
    cy += (ty - cy) * ease
    el.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`
    raf = requestAnimationFrame(loop)
  }
  window.addEventListener('pointermove', onMove, { passive: true })
  raf = requestAnimationFrame(loop)
  return () => {
    cancelAnimationFrame(raf)
    window.removeEventListener('pointermove', onMove)
    el.style.transform = ''
  }
}

/* ── 3. magnetic：磁吸（指针靠近时元素被"吸"过去） ────────────────────── */
export function magnetic(el, { x = 0.28, y = 0.42, max = 22 } = {}) {
  if (!isElement(el) || prefersReduced()) return () => {}
  if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return () => {}

  const clamp = (v) => Math.max(-max, Math.min(max, v))
  const onMove = (e) => {
    const r = el.getBoundingClientRect()
    const dx = clamp((e.clientX - r.left - r.width / 2) * x)
    const dy = clamp((e.clientY - r.top - r.height / 2) * y)
    el.style.transform = `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px)`
  }
  const onLeave = () => {
    el.style.transform = ''
  }
  el.addEventListener('pointermove', onMove)
  el.addEventListener('pointerleave', onLeave)
  return () => {
    el.removeEventListener('pointermove', onMove)
    el.removeEventListener('pointerleave', onLeave)
    el.style.transform = ''
  }
}

/* ── 4. trace：笔锋描绘（SVG 路径从左到右写出） ───────────────────────── */
/**
 * 进入视口后把 stroke-dashoffset 从长度推到 0；需要路径上已有 --len。
 * 这是"数据呈现"的专用原语（光变曲线、进度、里程）。
 */
export function traceOnScroll(svgOrGroup, { duration = 1.9 } = {}) {
  const host = svgOrGroup
  if (!isElement(host) || typeof host.querySelectorAll !== 'function') return () => {}
  const paths = host.querySelectorAll('.trace-path')
  if (!paths.length) return () => {}

  const draw = () => {
    paths.forEach((p) => {
      const len = p.getTotalLength ? p.getTotalLength() : 0
      if (!len) return
      p.style.setProperty('--len', String(Math.ceil(len)))
      if (prefersReduced()) {
        p.style.strokeDasharray = 'none'
        p.style.strokeDashoffset = '0'
        return
      }
      p.style.strokeDasharray = String(Math.ceil(len))
      p.style.strokeDashoffset = String(Math.ceil(len))
      p.style.transition = `stroke-dashoffset ${duration}s var(--e-settle)`
      // 下一帧再推，保证起始态被渲染过（否则过渡不触发）
      requestAnimationFrame(() => {
        p.style.strokeDashoffset = '0'
      })
    })
    host.classList.add('traced')
  }

  if (prefersReduced() || !('IntersectionObserver' in window)) {
    draw()
    return () => {}
  }
  const io = new IntersectionObserver(
    (entries) => {
      if (!entries[0].isIntersecting) return
      draw()
      io.disconnect()
    },
    { threshold: 0.3 },
  )
  io.observe(host)
  return () => io.disconnect()
}

/* ── 5. scan：扫描线（等待上游的诚实表达） ─────────────────────────────── */
/** 纯粹是 CSS 类的开关；这里只负责在 reduced-motion 时立刻结束 */
export function scanGuard(el) {
  if (!isElement(el)) return
  if (prefersReduced()) el.classList.add('scan-off')
}

/* ── 6. focus：焦点墨圈（键盘可达性的可见化） ─────────────────────────── */
/** 给容器内所有可聚焦元素加上统一焦点样式类（样式在 base.css 里） */
export function focusRing(container) {
  if (!isElement(container)) return () => {}
  const els = container.querySelectorAll('a, button, [tabindex]:not([tabindex="-1"])')
  els.forEach((el) => el.classList.add('focus-ring'))
  return () => els.forEach((el) => el.classList.remove('focus-ring'))
}

/* ── 组合式：把一个 ref 元素接上多条原语，卸载时自动清理 ───────────────── */
export function useMotion(setup) {
  const el = ref(null)
  let stops = []
  onMounted(() => {
    const node = el.value
    if (!node) return
    const result = setup(node)
    stops = Array.isArray(result) ? result : result ? [result] : []
  })
  onBeforeUnmount(() => stops.forEach((fn) => typeof fn === 'function' && fn()))
  return el
}
