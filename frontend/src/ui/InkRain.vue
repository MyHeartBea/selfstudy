<script setup>
/**
 * InkRain —— 内容文字雨（Ink Dynasty 案例的转译）
 * ===========================================================================
 * 「内容即装饰」：落下的不是抽象粒子，而是刚复习过的题干里的真实汉字。
 * 复习完成时，这些字从纸面上方缓缓落下、晕开、消失 —— 这一轮复习的内容
 * 化作一场墨雨。Canvas 2D 单层实现，纪律与 AmbientLayer 相同：
 *   · rAF 只在有活着的字滴时运转，落完即停（追平自停模式）
 *   · visibilitychange / 组件卸载立即停
 *   · prefers-reduced-motion 下一律不渲染
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /* 参与落雨的汉字（调用方从题目文本里提取去重） */
  chars: { type: Array, default: () => [] },
  /* 同屏字滴上限：容器高度越小应当越小 */
  max: { type: Number, default: 30 },
})

const wrapEl = ref(null)
const canvasEl = ref(null)

let ctx = null
let raf = 0
let running = false
let drops = []
let spawnAt = 0
let dpr = 1

function pickChar() {
  return props.chars[(Math.random() * props.chars.length) | 0] || '墨'
}

function spawnDrop() {
  const el = wrapEl.value
  if (!el || !props.chars.length) return
  const w = el.clientWidth
  const h = el.clientHeight
  if (!w || !h) return
  drops.push({
    ch: pickChar(),
    x: Math.random() * w,
    y: -24,
    v: 22 + Math.random() * 30, // px/s：缓落
    size: 13 + Math.random() * 15,
    alpha: 0.1 + Math.random() * 0.12,
    rot: (Math.random() - 0.5) * 0.5,
  })
}

let last = 0

function loop(now) {
  if (!running || !ctx) return
  const el = wrapEl.value
  if (!el) return
  const h = el.clientHeight
  const dt = Math.min(0.05, (now - last) / 1000 || 0.016)
  last = now
  ctx.clearRect(0, 0, el.clientWidth, h)
  // 补员：平均每 240ms 一滴，直到上限
  if (now - spawnAt > 240 && drops.length < props.max) {
    spawnDrop()
    spawnAt = now
  }
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  drops = drops.filter((d) => d.y < h + 30 && d.alpha > 0.01)
  for (const d of drops) {
    d.y += d.v * dt
    // 接近底部时晕开消散：字号增大、透明度衰减
    const tail = Math.max(0, (d.y - (h - 90)) / 90)
    const a = d.alpha * (1 - tail)
    const s = d.size * (1 + tail * 0.5)
    ctx.save()
    ctx.globalAlpha = a
    ctx.translate(d.x, d.y)
    ctx.rotate(d.rot * tail)
    ctx.font = `${s}px "Noto Serif SC", "Songti SC", serif`
    ctx.fillStyle = getInk()
    ctx.fillText(d.ch, 0, 0)
    ctx.restore()
  }
  if (drops.length) {
    raf = requestAnimationFrame(loop)
  } else {
    // 自停：清屏后不再排帧，props.chars 变化时由 watcher 重新唤醒
    running = false
    raf = 0
    ctx.clearRect(0, 0, el.clientWidth, h)
  }
}

let inkColor = ''

function getInk() {
  return inkColor
}

function readInk() {
  inkColor =
    getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() || '#2c2822'
}

function start() {
  if (running || !ctx) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (!props.chars.length) return
  readInk()
  resize()
  running = true
  last = performance.now()
  spawnAt = 0
  raf = requestAnimationFrame(loop)
}

function stop() {
  running = false
  if (raf) cancelAnimationFrame(raf)
  raf = 0
  drops = []
  if (ctx && canvasEl.value) ctx.clearRect(0, 0, canvasEl.value.width, canvasEl.value.height)
}

function resize() {
  const el = wrapEl.value
  const cv = canvasEl.value
  if (!el || !cv) return
  dpr = Math.min(2, window.devicePixelRatio || 1)
  cv.width = el.clientWidth * dpr
  cv.height = el.clientHeight * dpr
  ctx = cv.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function onVisibility() {
  if (document.visibilityState === 'hidden') stop()
  else start()
}

onMounted(() => {
  document.addEventListener('visibilitychange', onVisibility)
  start()
})

onBeforeUnmount(() => {
  stop()
  document.removeEventListener('visibilitychange', onVisibility)
})

defineExpose({ start })
</script>

<template>
  <div ref="wrapEl" class="ink-rain" aria-hidden="true">
    <canvas ref="canvasEl" class="ink-rain__cv"></canvas>
  </div>
</template>

<style scoped>
.ink-rain {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border-radius: inherit;
  pointer-events: none;
}
.ink-rain__cv {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
</style>
