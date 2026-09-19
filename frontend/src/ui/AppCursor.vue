<!--
  AppCursor —— 毛笔光标（「数字文房」的门面件）
  ===========================================================================
  用户点名要"图形化、像毛笔"的指针，取代之前的"小圆点/圆环"。
  设计：
    · 笔身用 Lucide `brush` 的原始 path（仓库图标纪律：只从 Lucide 取形），
      30px，斜握姿态；**笔锋尖端就是指针热区** —— 指到哪，笔锋落在哪
    · 悬停可点元素：笔提起并转朱砂（is-hover），锋下浮出细墨环标示目标
    · 按下：压笔（笔身前倾 + 下沉），锋尖滴墨 —— 一圈墨晕向外洇开（一次性）
  纪律（沿袭上一版）：
    · 位置 transform 驱动（不触发布局），rAF + lerp 0.2 跟随
    · 触屏 / prefers-reduced-motion 下整个组件不渲染
    · body.km-custom-cursor 挂载成功才隐藏原生指针（脚本失效时指针仍在）
-->
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const cur = ref(null)

let raf = 0
let running = true
let x = 0
let y = 0
let cx = 0
let cy = 0
let hovering = false
let pressed = false

const HIT = 'a, button, [role="button"], input, select, textarea, [data-magnetic], .row, .card'

function allowed() {
  if (typeof window === 'undefined') return false
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  // 只在精确指针（鼠标）上启用
  return matchMedia('(hover: hover) and (pointer: fine)').matches
}

function onMove(e) {
  x = e.clientX
  y = e.clientY
  const t = e.target
  hovering = !!(t && t.closest && t.closest(HIT))
}

function onDown() {
  pressed = true
}
function onUp() {
  pressed = false
}
function onLeave() {
  if (cur.value) cur.value.style.opacity = '0'
}
function onEnter() {
  if (cur.value) cur.value.style.opacity = '1'
}

function loop() {
  if (!running) return
  cx += (x - cx) * 0.2
  cy += (y - cy) * 0.2
  const el = cur.value
  if (el) {
    el.style.transform = `translate3d(${cx.toFixed(1)}px, ${cy.toFixed(1)}px, 0)`
    el.classList.toggle('is-hover', hovering)
    el.classList.toggle('is-press', pressed)
  }
  raf = requestAnimationFrame(loop)
}

function onVisibility() {
  running = document.visibilityState === 'visible'
  if (running) raf = requestAnimationFrame(loop)
  else cancelAnimationFrame(raf)
}

onMounted(() => {
  if (!allowed()) return
  // 挂载成功才隐藏原生指针（安全网：脚本没跑起来时原生指针仍在）
  document.body.classList.add('km-custom-cursor')
  window.addEventListener('pointermove', onMove, { passive: true })
  window.addEventListener('pointerdown', onDown, { passive: true })
  window.addEventListener('pointerup', onUp, { passive: true })
  document.addEventListener('visibilitychange', onVisibility)
  document.addEventListener('pointerleave', onLeave)
  document.addEventListener('pointerenter', onEnter)
  raf = requestAnimationFrame(loop)
})

onBeforeUnmount(() => {
  document.body.classList.remove('km-custom-cursor')
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerdown', onDown)
  window.removeEventListener('pointerup', onUp)
  document.removeEventListener('visibilitychange', onVisibility)
  document.removeEventListener('pointerleave', onLeave)
  document.removeEventListener('pointerenter', onEnter)
})
</script>

<template>
  <span ref="cur" class="cur" aria-hidden="true">
    <i class="cur__ripple"></i>
    <i class="cur__ring"></i>
    <!-- Lucide "brush"：斜握笔杆，锋在左下 —— 左下角对齐指针热区 -->
    <svg
      class="cur__brush"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="m9.06 11.9 8.07-8.06a2.85 2.85 0 1 1 4.03 4.03l-8.06 8.08" />
      <path
        d="M7.07 14.94c-1.66 0-3 1.35-3 3.02 0 1.33-2.5 1.52-2 2.02 1.08 1.1 2.49 2.02 4 2.02 2.2 0 4-1.8 4-4.04a3.01 3.01 0 0 0-3-3.02z"
      />
    </svg>
    <i class="cur__tip"></i>
  </span>
</template>

<style scoped>
/* 锚点：0x0 元素钉在指针坐标上，笔锋/墨环都相对它定位 */
.cur {
  position: fixed;
  top: 0;
  left: 0;
  width: 0;
  height: 0;
  z-index: 9500;
  pointer-events: none;
  transform: translate3d(-200px, -200px, 0);
  color: var(--ink);
  opacity: 1;
  will-change: transform;
}

/* 笔身：锋尖（图标左下）对齐锚点；默认斜握 6° */
.cur__brush {
  position: absolute;
  left: -7px;
  top: -24px;
  width: 30px;
  height: 30px;
  transform: rotate(6deg);
  transform-origin: 20% 78%;
  filter: drop-shadow(0 1px 2px color-mix(in srgb, var(--ink) 24%, transparent));
  transition:
    transform 0.35s var(--spring),
    color 0.25s var(--ease);
}

/* 锋尖墨点：落在锚点上的那粒墨，保证"指到哪"的精度感 */
.cur__tip {
  position: absolute;
  left: -2.5px;
  top: -2.5px;
  width: 5px;
  height: 5px;
  border-radius: 50% 50% 50% 0;
  background: var(--ink);
  transform: rotate(-45deg);
  transition: background 0.25s var(--ease);
}

/* 悬停可点元素：提笔转朱砂 + 锋下浮出细墨环 */
.cur.is-hover {
  color: var(--accent);
}
.cur.is-hover .cur__brush {
  transform: rotate(-7deg) scale(1.1) translate(-1px, -2px);
}
.cur.is-hover .cur__tip {
  background: var(--accent);
}
.cur__ring {
  position: absolute;
  left: -17px;
  top: -17px;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1.5px solid color-mix(in srgb, var(--accent) 55%, transparent);
  opacity: 0;
  transform: scale(0.55);
  transition:
    opacity var(--dur-2) var(--ease),
    transform var(--dur-3) var(--spring);
}
.cur.is-hover .cur__ring {
  opacity: 1;
  transform: scale(1);
}

/* 按下：压笔 —— 笔身前倾下沉，锋尖滴墨（墨晕一次性扩散） */
.cur.is-press .cur__brush {
  transform: rotate(14deg) scale(0.94) translate(1.5px, 2.5px);
}
.cur.is-press .cur__ripple {
  position: absolute;
  left: -14px;
  top: -14px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--accent);
  opacity: 0;
  animation: cur-ripple 0.55s var(--ease-exit) forwards;
}
@keyframes cur-ripple {
  from {
    opacity: 0.8;
    transform: scale(0.9);
  }
  to {
    opacity: 0;
    transform: scale(2.3);
  }
}

@media (pointer: coarse), (prefers-reduced-motion: reduce) {
  .cur {
    display: none;
  }
}
</style>
