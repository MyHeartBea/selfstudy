/**
 * 物理动效原语（physics.js）—— 弹簧 / 阻尼 / 惯性 / 错峰
 * ---------------------------------------------------------------------------
 * 为什么单独一层：用户明确要求"物理感动效：弹簧、惯性、阻尼、延迟、错峰"。
 * 之前我用的是 **CSS cubic-bezier**（那是"曲线"，不是物理）——
 * 差别在于：曲线到点即停，弹簧有**速度、过冲、回弹**；拖拽松手要有**惯性衰减**。
 * 这两件事 CSS 做不到（CSS transition 无法从"当前速度"续接），必须用 rAF 积分。

 * 本文件只做三件事，都只写 transform / opacity（不触发布局）：
 *   1. spring()      —— 弹簧积分器（质量-弹簧-阻尼二阶系统），支持中断续接
 *   2. inertia()     —— 拖拽/甩动的惯性衰减
 *   3. stagger()     —— 错峰调度（把 N 个任务的起始时间错开）
 *
 * 物理模型（半隐式欧拉，稳定且够快）：
 *     a = (-k * (x - target) - c * v) / m
 *     v += a * dt
 *     x += v * dt
 *   k = 刚度，c = 阻尼，m = 质量。
 *   本项目用"感知参数"（stiffness / damping / mass）而不是让人调 k/c，更好配。
 *
 * 关键细节（踩过的坑）：
 *   · **dt 必须夹紧**：切到后台再回来时 dt 可能是几秒，积分会炸（元素瞬间飞走）。
 *     所以 clamp dt 到 1/30 秒。
 *   · **可中断续接**：拖拽中重新设定目标时保留当前速度（v 不清零），
 *     这才是"手感"的来源；清零会变成"每次重新起步"。
 *   · reduced-motion 下直接落到目标值（瞬时到位，信息不丢）。
 */

export function prefersReducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** 常用手感预设：名字即用途，避免到处调数字 */
export const SPRING = {
  /** 落定：轻微过冲，用于卡片/弹层到位 */
  settle: { stiffness: 210, damping: 26, mass: 1 },
  /** 拖拽跟手：更硬、几乎不过冲 */
  track: { stiffness: 520, damping: 42, mass: 1 },
  /** 强调：明显回弹，用于确认/命中 */
  pop: { stiffness: 340, damping: 18, mass: 1 },
  /** 柔和：大位移、无过冲 */
  glide: { stiffness: 120, damping: 24, mass: 1 },
}

/**
 * 弹簧积分器。
 * @param {number} from 起始值
 * @param {number} to 目标值
 * @param {{stiffness?:number, damping?:number, mass?:number, velocity?:number,
 *          onUpdate:(v:number)=>void, onDone?:()=>void, restDelta?:number}} opts
 * @returns {{ retarget:(t:number, keepVelocity?:boolean)=>void, stop:()=>void }}
 */
export function spring(from, to, opts) {
  const { stiffness = 210, damping = 26, mass = 1 } = opts
  const restDelta = opts.restDelta ?? 0.01
  const onUpdate = opts.onUpdate || (() => {})
  const onDone = opts.onDone

  if (prefersReducedMotion()) {
    onUpdate(to)
    onDone && onDone()
    return { retarget: () => {}, stop: () => {} }
  }

  let x = from
  let target = to
  let v = opts.velocity || 0
  let raf = 0
  let last = performance.now()
  let stopped = false

  const step = (now) => {
    if (stopped) return
    // dt 夹紧：后台标签页回来时 dt 可能极大，积分会发散
    const dt = Math.min((now - last) / 1000, 1 / 30)
    last = now

    const a = (-stiffness * (x - target) - damping * v) / mass
    v += a * dt
    x += v * dt

    // 静止判定：位移与速度都足够小
    if (Math.abs(x - target) < restDelta && Math.abs(v) < restDelta * 4) {
      x = target
      onUpdate(x)
      stopped = true
      onDone && onDone()
      return
    }
    onUpdate(x)
    raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)

  return {
    /** 重新设定目标；keepVelocity=true 时保留当前速度（拖拽手感的关键） */
    retarget(next, keepVelocity = true) {
      target = next
      if (!keepVelocity) v = 0
      if (stopped) {
        stopped = false
        last = performance.now()
        raf = requestAnimationFrame(step)
      }
    },
    stop() {
      stopped = true
      cancelAnimationFrame(raf)
    },
  }
}

/**
 * 惯性衰减：拖拽松手后的滑行。
 * 按速度衰减到阈值后停止，并在每帧把剩余位移交给调用方。
 * @returns {{stop:()=>void}}
 */
export function inertia(initialVelocity, opts) {
  const { friction = 0.94, minVelocity = 0.02 } = opts || {}
  const onUpdate = opts?.onUpdate || (() => {})
  const onDone = opts?.onDone

  if (prefersReducedMotion()) {
    onDone && onDone()
    return { stop: () => {} }
  }

  let v = initialVelocity
  let raf = 0
  let last = performance.now()
  let stopped = false

  const step = (now) => {
    if (stopped) return
    const dt = Math.min((now - last) / 1000, 1 / 30)
    last = now
    // 每帧按摩擦系数衰减（与帧率无关的写法：pow(friction, dt*60)）
    v *= Math.pow(friction, dt * 60)
    onUpdate(v * dt)
    if (Math.abs(v) < minVelocity) {
      stopped = true
      onDone && onDone()
      return
    }
    raf = requestAnimationFrame(step)
  }
  raf = requestAnimationFrame(step)
  return {
    stop() {
      stopped = true
      cancelAnimationFrame(raf)
    },
  }
}

/**
 * 错峰调度：把 [0, n) 的起始时间按 stagger 毫秒错开，
 * 前 delay 毫秒内不动，之后归零交给调用方自己的动画。
 * 返回一个 start(i) - 该元素还需等待的毫秒数。
 */
export function stagger(n, stepMs = 55, { maxTotal = 520 } = {}) {
  const capped = Math.min(stepMs, maxTotal / Math.max(1, n - 1))
  return (i) => Math.round(i * capped)
}

/**
 * 把"弹簧驱动一个元素的 translateY + opacity"这件事封装好，
 * 用于卡片/列表项的入场（expo-out 的替代品，但带真实弹簧手感）。
 */
export function springIn(el, { delay = 0, y = 26, preset = 'settle' } = {}) {
  if (!el) return () => {}
  if (prefersReducedMotion()) {
    el.style.opacity = '1'
    el.style.transform = 'none'
    return () => {}
  }
  const cfg = SPRING[preset] || SPRING.settle
  el.style.opacity = '0'
  el.style.transform = `translate3d(0, ${y}px, 0)`
  let sp = null
  let timer = 0
  const run = () => {
    el.style.opacity = '1'
    sp = spring(y, 0, {
      ...cfg,
      onUpdate: (v) => {
        el.style.transform = `translate3d(0, ${v.toFixed(2)}px, 0)`
      },
      onDone: () => {
        el.style.transform = 'none'
      },
    })
  }
  if (delay > 0) timer = setTimeout(run, delay)
  else run()
  return () => {
    clearTimeout(timer)
    if (sp) sp.stop()
  }
}
