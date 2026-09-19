<script setup>
/**
 * FlipCard —— 共享 3D 翻牌基件（墨韵 3.4）
 * ===========================================================================
 * 此前生词本自写一套 preserve-3d 翻面、公式背诵又用"按钮 reveal"，
 * 两处语言不一。抽成本件后两页同构：
 *   · 点卡片翻面（interactive），也可只受控展示（interactive=false）
 *   · 翻转只动 transform（preserve-3d + rotateY），合成层，60fps
 *   · 高度由使用方经 --flip-h 控制（默认 280px），宽度随容器
 * 键盘不内置：由使用方的键盘流负责（生词本有空格/123，公式有左右方向键），
 * 避免两套键盘处理叠加导致双重切换。
 */
defineProps({
  flipped: { type: Boolean, default: false },
  interactive: { type: Boolean, default: true },
})
const emit = defineEmits(['flip'])
</script>

<template>
  <div
    class="flip-stage"
    :class="{ flipped }"
    :role="interactive ? 'button' : undefined"
    :tabindex="interactive ? 0 : undefined"
    :aria-pressed="interactive ? flipped : undefined"
    @click="interactive && emit('flip')"
  >
    <div class="flip-inner">
      <div class="flip-face flip-front"><slot name="front"></slot></div>
      <div class="flip-face flip-back"><slot name="back"></slot></div>
    </div>
  </div>
</template>

<style scoped>
.flip-stage {
  height: var(--flip-h, 280px);
  perspective: 1200px;
  cursor: pointer;
  outline: none;
  /* 横向拖拽归本组件（生词本 swipe），竖向滚动留给页面 */
  touch-action: pan-y;
}
.flip-stage:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: var(--r-lg);
}
.flip-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.55s var(--ease-move);
}
.flip-stage.flipped .flip-inner {
  transform: rotateY(180deg);
}
.flip-face {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 22px;
  border-radius: var(--r-lg);
  background: var(--surface);
  border: 1px solid var(--line-strong);
  box-shadow: var(--shadow-1);
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  overflow: hidden;
  text-align: center;
}
.flip-face.flip-back {
  position: absolute;
  transform: rotateY(180deg);
}
@media (prefers-reduced-motion: reduce) {
  .flip-inner {
    transition: none;
  }
}
</style>
