/**
 * 手写 canvas 礼花引擎（零依赖）。
 * confetti.burst(x, y, { count, spread, power, colors })  在指定坐标迸发
 * confetti.rain({ duration })                              全屏持续飘落
 */

let canvas = null
let ctx = null
let particles = []
let rafId = null

const DEFAULT_COLORS = [
  '#c2402a',
  '#e0604a',
  '#a16207',
  '#d0a03f',
  '#1a7f42',
  '#2f6db3',
  '#6d5bd0',
  '#fffdf8',
]

function ensureCanvas() {
  if (canvas) return
  canvas = document.createElement('canvas')
  canvas.style.cssText =
    'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:1500;'
  document.body.appendChild(canvas)
  ctx = canvas.getContext('2d')
  resize()
  window.addEventListener('resize', resize)
}

function resize() {
  if (!canvas) return
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  canvas.width = window.innerWidth * dpr
  canvas.height = window.innerHeight * dpr
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function spawn(x, y, opts = {}) {
  const count = opts.count || 28
  const spread = opts.spread || Math.PI / 2.2
  const angle = opts.angle ?? -Math.PI / 2
  const power = opts.power || 9
  const colors = opts.colors || DEFAULT_COLORS
  for (let i = 0; i < count; i++) {
    const a = angle + (Math.random() - 0.5) * spread
    const v = power * (0.5 + Math.random() * 0.8)
    particles.push({
      x,
      y,
      vx: Math.cos(a) * v,
      vy: Math.sin(a) * v,
      size: 3 + Math.random() * 5,
      color: colors[(Math.random() * colors.length) | 0],
      rot: Math.random() * Math.PI * 2,
      vr: (Math.random() - 0.5) * 0.3,
      gravity: 0.18 + Math.random() * 0.12,
      drag: 0.985,
      life: 1,
      decay: 0.008 + Math.random() * 0.01,
      shape: Math.random() > 0.35 ? 'rect' : 'circle',
    })
  }
}

function tick() {
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  particles = particles.filter((p) => p.life > 0 && p.y < window.innerHeight + 40)
  for (const p of particles) {
    p.vx *= p.drag
    p.vy = p.vy * p.drag + p.gravity
    p.x += p.vx
    p.y += p.vy
    p.rot += p.vr
    p.life -= p.decay
    ctx.save()
    ctx.globalAlpha = Math.max(0, Math.min(1, p.life * 1.6))
    ctx.translate(p.x, p.y)
    ctx.rotate(p.rot)
    ctx.fillStyle = p.color
    if (p.shape === 'rect') {
      ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2)
    } else {
      ctx.beginPath()
      ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2)
      ctx.fill()
    }
    ctx.restore()
  }
  if (particles.length) {
    rafId = requestAnimationFrame(tick)
  } else {
    rafId = null
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }
}

function kick() {
  ensureCanvas()
  if (rafId === null) rafId = requestAnimationFrame(tick)
}

export const confetti = {
  /** 从视口下方两侧向上喷射（庆祝感最强） */
  celebrate(opts = {}) {
    kick()
    const h = window.innerHeight
    const w = window.innerWidth
    spawn(w * 0.12, h + 10, { angle: -Math.PI / 3, power: 15, count: opts.count ?? 40, spread: Math.PI / 5 })
    spawn(w * 0.88, h + 10, { angle: (-Math.PI * 2) / 3, power: 15, count: opts.count ?? 40, spread: Math.PI / 5 })
    if (opts.center !== false) {
      setTimeout(() => spawn(w * 0.5, h * 0.35, { angle: -Math.PI / 2, power: 8, count: 24 }), 180)
    }
  },
  /** 在元素中心迸发（答对一题的小奖励） */
  burstAtElement(el, opts = {}) {
    if (!el) return
    kick()
    const rect = el.getBoundingClientRect()
    spawn(rect.left + rect.width / 2, rect.top + rect.height / 2, {
      count: opts.count ?? 22,
      power: opts.power ?? 6.5,
    })
  },
}
