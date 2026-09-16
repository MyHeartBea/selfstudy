/** * 自定义光标（SkyCursor） *
--------------------------------------------------------------------------- * 小圆点 + lerp
跟随；命中交互元素时放大并变为红移色。 * * **与 SOLARIS
参考实现的一个关键差异**：这里**不隐藏原生光标**。 * 参考稿用 body{cursor:none}
隐藏系统指针，一旦自定义光标的 JS 异常，用户就完全失去指针。 *
这是每天要用的表单/键盘高频工具，所以我让两者并存：圆点跟随 + 原生指针保留。 * *
只在精确指针设备（hover: hover + pointer: fine）启用；触屏与 reduced-motion 下完全不初始化。 *
实现要点：位移只改 transform（合成层），rAF 单循环，不做任何布局读取。 */
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const dot = ref(null)

let raf = 0
let mx = 0
let my = 0
let cx = 0
let cy = 0
let active = false

const HOT = 'a,button,[data-magnetic],.row,.card,.tile,[role="button"]'

function onMove(e) {
  mx = e.clientX
  my = e.clientY
  if (!active && dot.value) {
    active = true
    dot.value.classList.add('on')
  }
}

function onOver(e) {
  if (!dot.value) return
  const hot = e.target.closest && e.target.closest(HOT)
  dot.value.classList.toggle('hot', !!hot)
}

function onLeave() {
  active = false
  dot.value?.classList.remove('on')
}

function loop() {
  cx += (mx - cx) * 0.19
  cy += (my - cy) * 0.19
  if (dot.value) {
    dot.value.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`
  }
  raf = requestAnimationFrame(loop)
}

onMounted(() => {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
  if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return

  mx = cx = window.innerWidth / 2
  my = cy = window.innerHeight / 2
  window.addEventListener('pointermove', onMove, { passive: true })
  document.addEventListener('pointerover', onOver, { passive: true })
  document.addEventListener('pointerleave', onLeave)
  raf = requestAnimationFrame(loop)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onMove)
  document.removeEventListener('pointerover', onOver)
  document.removeEventListener('pointerleave', onLeave)
})
</script>

<template>
  <span ref="dot" class="sky-cursor" aria-hidden="true"></span>
</template>

<style scoped>
.sky-cursor {
  position: fixed;
  left: 0;
  top: 0;
  width: 9px;
  height: 9px;
  margin: -4.5px 0 0 -4.5px;
  border-radius: 50%;
  background: var(--ink-0);
  z-index: var(--z-cursor);
  pointer-events: none;
  opacity: 0;
  transition:
    width 0.42s var(--e-settle),
    height 0.42s var(--e-settle),
    background 0.42s var(--e-settle),
    margin 0.42s var(--e-settle),
    opacity 0.3s;
  will-change: transform;
}
.sky-cursor.on {
  opacity: 1;
}
.sky-cursor.hot {
  width: 46px;
  height: 46px;
  margin: -23px 0 0 -23px;
  background: var(--redshift);
  box-shadow: var(--glow);
}
</style>
