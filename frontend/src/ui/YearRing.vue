<script setup>
/**
 * YearRing —— 复习数据年轮（easylog「动效讲概念」的转译）
 * ===========================================================================
 * 本轮复习的每一道题化作年轮上的一段弧：答对 = 朱砂弧，答错 = 淡墨弧。
 * 印章落下后，年轮按顺时针生长一圈 —— "这次复习"被记进纸的年轮里。
 * 纪律：单 Canvas，rAF 只在生长动画期间运转（1.4s 后自停）；
 * reduced-motion 下直接静态绘制完整年轮，不做生长。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /* 本轮题量（弧的数量） */
  total: { type: Number, default: 0 },
  /* 答对数（前 correct 段为朱砂？不 —— 按顺序不表达对错，改为：错题弧
     均匀穿插在年轮上，避免"对的全在右边"的暗示） */
  wrong: { type: Number, default: 0 },
  size: { type: Number, default: 300 },
})

const cvEl = ref(null)
let raf = 0

function draw(progress) {
  const cv = cvEl.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  const S = props.size
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  if (cv.width !== S * dpr) {
    cv.width = S * dpr
    cv.height = S * dpr
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, S, S)
  const total = Math.max(1, props.total)
  const cx = S / 2
  const cy = S / 2
  const r = S / 2 - 10
  const gap = total > 1 ? 0.1 : 0.3 // 弧间留缝
  const seg = (Math.PI * 2) / total
  // 错题弧的索引：均匀穿插
  const wrongSet = new Set()
  if (props.wrong > 0) {
    const step = total / props.wrong
    for (let i = 0; i < props.wrong; i++) wrongSet.add(Math.floor(i * step))
  }
  // 读主题墨色
  const ink = getComputedStyle(document.documentElement).getPropertyValue('--ink').trim()
  const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
  ctx.lineWidth = 7
  ctx.lineCap = 'round'
  const shown = Math.max(1, Math.ceil(total * progress))
  for (let i = 0; i < shown; i++) {
    const a0 = -Math.PI / 2 + i * seg + gap / 2
    const a1 = -Math.PI / 2 + (i + 1) * seg - gap / 2
    ctx.strokeStyle = wrongSet.has(i) ? ink : accent
    ctx.globalAlpha = wrongSet.has(i) ? 0.28 : 0.8
    ctx.beginPath()
    ctx.arc(cx, cy, r, a0, Math.max(a0 + 0.02, a1))
    ctx.stroke()
  }
  ctx.globalAlpha = 1
}

function start() {
  draw(1)
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const t0 = performance.now()
  const DUR = 1400
  const ease = (p) => 1 - Math.pow(1 - p, 3)
  const step = (now) => {
    const p = Math.min(1, (now - t0) / DUR)
    draw(ease(p))
    if (p < 1) raf = requestAnimationFrame(step)
    else raf = 0
  }
  // 等印章落地（第 5 拍 ≈ 350ms + 600ms）再开始生长
  setTimeout(() => {
    raf = requestAnimationFrame(step)
  }, 1000)
}

onMounted(start)
onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
})
</script>

<template>
  <canvas
    ref="cvEl"
    class="year-ring"
    :style="{ width: size + 'px', height: size + 'px' }"
    aria-hidden="true"
  ></canvas>
</template>

<style scoped>
.year-ring {
  display: block;
}
</style>
