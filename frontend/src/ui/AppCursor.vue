<!--
  AppCursor —— 自定义光标（学参考稿的命中扩张）
  ===========================================================================
  学自参考稿：
    · 命中可交互元素时光标从 9px **扩张到 54px** 并转强调色
      —— 这是明确的"这里可点"回执，比我上一版 2.1 倍缩放大胆得多
    · **直径过渡**而不是 scale：小圆点用 scale 放大会糊边（参考稿也是改宽高）
    · 按下时再收一点（34px），给点击一个可见回执

  与 v2 的适配：
    · 强调色用 v2 的 --accent（朱砂），不引入新颜色
    · **仍不移除原生光标**（与参考稿不同，它写了 cursor:none）：
      这是可用性底线 —— JS 失效时用户不至于"没有指针"。
      若你要严格照参考稿隐藏原生指针，说一声我改。
    · 触屏 / prefers-reduced-motion 下不渲染

  位置用 transform 驱动（不触发布局），rAF + lerp 0.2 跟随。
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
    el.style.transform = `translate3d(${cx.toFixed(1)}px, ${cy.toFixed(1)}px, 0) translate(-50%, -50%)`
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
  <span ref="cur" class="cur" aria-hidden="true"></span>
</template>

<style scoped>
.cur {
  position: fixed;
  top: 0;
  left: 0;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--ink);
  z-index: 9500;
  pointer-events: none;
  transform: translate3d(-200px, -200px, 0);
  transition:
    width 0.45s var(--ease),
    height 0.45s var(--ease),
    background 0.45s var(--ease),
    opacity 0.3s ease;
  will-change: transform;
}
/* 命中：扩张到 54px，但**改为细描边环 + 透明内芯**。
   为什么不像参考稿那样直接变实心强调色：参考稿的底色是 #060607（近黑），
   实心 #FF4D1C 在暗底上是"亮起来"；v2 是米色底，大面积实心朱砂会变成
   一团刺眼的红 —— 这就是用户说"鼠标太丑"的原因。
   在浅底上改用"环"：同样传达"可点"，但只占一圈线。 */
.cur.is-hover {
  width: 54px;
  height: 54px;
  background: transparent;
  border: 1.5px solid var(--accent);
  box-shadow: inset 0 0 0 0.5px color-mix(in srgb, var(--accent) 35%, transparent);
}
/* 命中时内芯留一个极小的实心点，保持"指针尖"的位置感 */
.cur.is-hover::after {
  content: '';
  position: absolute;
  inset: 50% auto auto 50%;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
  transform: translate(-50%, -50%);
}
/* 按下：再收一点 */
.cur.is-press {
  width: 34px;
  height: 34px;
}

@media (pointer: coarse), (prefers-reduced-motion: reduce) {
  .cur {
    display: none;
  }
}
</style>
