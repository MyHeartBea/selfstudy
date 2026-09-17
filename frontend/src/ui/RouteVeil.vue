<!--
  RouteVeil —— 换页幕布（覆盖式转场）
  ===========================================================================
  用户反馈："换页动画太丑"。上一版的三个问题（都是我造成的）：

    ① **方向不一致**：扫入用 `transform-origin: bottom`（从下往上长），
       扫出用 `top`（从上沿收走）—— 两段方向相反，看着像"来回抽动"。
    ② **用 scaleY 会压扁内容**：幕布本身没有内容还好，但它把"扫过"做成了
       拉伸效果，边界发虚。
    ③ **两段之间有停顿**：afterEach 后才播，中间露出一帧新页面再盖住，
       节奏是"顿-抽-顿"，不是一次连贯的位移。

  正解：把幕布做成一个**很高的实体面板**，靠 `translateY` 整体平移。
    · 进场：面板原本在视口下方 100%，上移到 0（盖住）
    · 出场：从 0 继续上移到 -100%（移出视口上沿）
    → 两段是**同一个方向**（向上），读起来才是"翻过去一页"。
    · 位移用 translateY（不压缩内容，边界是硬的实色边）
    · 面板高度 100%，配合 overflow hidden 的容器，不会有露边

  时序（覆盖式，不是"扫一下"）：
    router.beforeEach 阶段：盖上幕布（120ms 内到位）
    幕布完全盖住后才放行导航 -> 换页在幕布后面发生（用户看不到跳变）
    导航完成后再让幕布继续上移离场
  这样用户永远看不到"新页面闪进来"的那一帧。
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** 'idle' | 'cover'（盖住）| 'reveal'（离场） */
  phase: { type: String, default: 'idle' },
})

const cls = computed(() => `veil--${props.phase}`)
</script>

<template>
  <div class="veil" :class="cls" aria-hidden="true">
    <div class="veil__face">
      <span class="veil__mark"></span>
      <span class="veil__label">载入</span>
      <span class="veil__line"></span>
    </div>
  </div>
</template>

<style scoped>
/* 容器只负责裁切，不参与动画 —— 避免露边 */
.veil {
  position: fixed;
  inset: 0;
  z-index: 9600;
  pointer-events: none;
  overflow: hidden;
  /* idle 时完全移出视口上方，不占任何视觉位置 */
  visibility: hidden;
}
.veil--cover,
.veil--reveal {
  visibility: visible;
}

/* 实体面板：整体平移，两段同向（都向上） */
.veil__face {
  position: absolute;
  inset: 0;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  transform: translateY(100%);
  will-change: transform;
}

/* 进场：从下方移入盖住（0.34s，快而稳） */
.veil--cover .veil__face {
  transform: translateY(0);
  transition: transform 0.34s cubic-bezier(0.22, 1, 0.36, 1);
}
/* 出场：从 0 继续向上移出（0.42s，稍慢，像"幕布拉走"） */
.veil--reveal .veil__face {
  transform: translateY(-100%);
  transition: transform 0.42s cubic-bezier(0.62, 0.02, 0.24, 1);
}

/* 幕布上的标记：一个小方块 + 文案 + 一条进度线，给等待一个可读的锚点 */
.veil__mark {
  width: 9px;
  height: 9px;
  background: var(--accent);
  border-radius: 1px;
  animation: veil-spin 1.4s var(--ease) infinite;
}
@keyframes veil-spin {
  0%,
  60% {
    transform: rotate(0) scale(1);
  }
  80% {
    transform: rotate(180deg) scale(0.7);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}
.veil__label {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11px;
  letter-spacing: 0.22em;
  color: var(--ink-3);
}
.veil__line {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 140px;
  height: 1px;
  margin-left: -70px;
  background: var(--accent);
  transform: scaleX(0);
  transform-origin: left;
}
.veil--cover .veil__line {
  transform: scaleX(1);
  transition: transform 0.32s var(--ease);
}

@media (prefers-reduced-motion: reduce) {
  .veil {
    display: none;
  }
}
</style>
