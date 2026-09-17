<!--
  AppCursor —— 自定义光标
  ===========================================================================
  用户要求"自定义光标"。实现要点（与在 v3 上定的原则一致）：

    1. **不移除原生光标**（不写 cursor:none）。自定义光标是"附加图层"，
       若 JS 失效或初始化失败，用户仍然有指针可用 —— 这是可用性底线。
    2. **lerp 跟随**（0.18）：光标有一点点"重量"，不是硬贴指针；这是"跟手"与
       "有物理感"的中间值。太快像贴纸，太慢像漂移。
    3. **命中可交互元素时放大并转朱砂**（a / button / [data-magnetic] / input 等）；
       按下时收缩 —— 给点击一个可见的回执。
    4. **触屏与 reduced-motion 不启用**（触屏没有 hover 语义；减弱动效时不该有跟随物）。
    5. 只动 transform，不触发布局；页面隐藏时暂停 rAF。

  与 v2 的关系：v2 原先没有光标层，这是新增；样式沿用 v2 令牌（--accent / --ease）。
-->
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const dot = ref(null)
const ring = ref(null)

let raf = 0
let running = true
let x = 0
let y = 0
let dx = 0
let dy = 0
let rx = 0
let ry = 0
let scale = 1
let targetScale = 1

function allowed() {
  if (typeof window === 'undefined') return false
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  // 触屏 / 无精确指针：不启用
  if (matchMedia('(pointer: coarse)').matches) return false
  if (!matchMedia('(pointer: fine)').matches) return false
  return true
}

const HIT = 'a, button, [role="button"], input, select, textarea, [data-magnetic], .card, .row'

function onMove(e) {
  x = e.clientX
  y = e.clientY
  const hit = e.target && e.target.closest ? e.target.closest(HIT) : null
  targetScale = hit ? 2.1 : 1
}

function onDown() {
  targetScale = (targetScale || 1) * 0.82
}
function onUp() {
  targetScale = 1
}

function loop() {
  if (!running) return
  // lerp：点几乎贴指针（0.5），圈更慢（0.16）-> 产生"拖尾"的层次
  dx += (x - dx) * 0.5
  dy += (y - dy) * 0.5
  rx += (x - rx) * 0.16
  ry += (y - ry) * 0.16
  scale += (targetScale - scale) * 0.14

  if (dot.value) {
    dot.value.style.transform = `translate3d(${dx.toFixed(1)}px, ${dy.toFixed(1)}px, 0) translate(-50%, -50%)`
  }
  if (ring.value) {
    ring.value.style.transform = `translate3d(${rx.toFixed(1)}px, ${ry.toFixed(1)}px, 0) translate(-50%, -50%) scale(${scale.toFixed(3)})`
  }
  raf = requestAnimationFrame(loop)
}

function onVisibility() {
  running = document.visibilityState === 'visible'
  if (running) {
    raf = requestAnimationFrame(loop)
  } else {
    cancelAnimationFrame(raf)
  }
}

onMounted(() => {
  if (!allowed()) return
  window.addEventListener('pointermove', onMove, { passive: true })
  window.addEventListener('pointerdown', onDown, { passive: true })
  window.addEventListener('pointerup', onUp, { passive: true })
  document.addEventListener('visibilitychange', onVisibility)
  raf = requestAnimationFrame(loop)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerdown', onDown)
  window.removeEventListener('pointerup', onUp)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <!-- 两个图层：内点 + 外圈。pointer-events:none 保证永远不拦截点击。 -->
  <div class="cur" aria-hidden="true">
    <span ref="ring" class="cur__ring"></span>
    <span ref="dot" class="cur__dot"></span>
  </div>
</template>

<style scoped>
.cur {
  position: fixed;
  inset: 0;
  z-index: 10000;
  pointer-events: none;
}
.cur__dot,
.cur__ring {
  position: absolute;
  top: 0;
  left: 0;
  border-radius: 50%;
  will-change: transform;
}
/* 内点：实心朱砂，小 */
.cur__dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
}
/* 外圈：极细描边，比点慢一拍 -> 形成"拖尾" */
.cur__ring {
  width: 30px;
  height: 30px;
  border: 1px solid var(--accent-ring, rgba(193, 74, 49, 0.35));
  transition: border-color 0.25s var(--ease);
}
/* 命中可交互元素时，外圈变实一点（scale 由 JS 驱动） */
.cur__ring::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--accent-soft, rgba(193, 74, 49, 0.1));
  opacity: 0;
  transition: opacity 0.25s var(--ease);
}
.cur__ring:hover::after {
  opacity: 1;
}
/* 这两个图层在触屏 / reduced-motion 下不渲染内容 */
@media (pointer: coarse), (prefers-reduced-motion: reduce) {
  .cur {
    display: none;
  }
}
</style>
