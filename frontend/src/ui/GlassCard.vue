<script setup>
/**
 * 玻璃卡片（墨韵 2.0 卡片基件）：渐变描边 + 玻璃拟态 + 悬停流光。
 * 防裁切规则：外层 .gcard 恒为 overflow:visible——骑缝徽章等悬浮元素
 * 一律放 #badge 插槽（挂在卡片包裹层）；卡片自身 overflow:hidden 只用于流光裁切。
 */
defineProps({
  hover: { type: Boolean, default: true }, // 悬浮上浮 + 流光
  pad: { type: Boolean, default: true }, // 默认内边距，网格布局时可关
})
</script>

<template>
  <div class="gcard" :class="{ hover, pad }">
    <div class="gcard-body">
      <slot></slot>
    </div>
    <slot name="badge"></slot>
  </div>
</template>

<style scoped>
.gcard {
  position: relative;
  min-width: 0;
}

.gcard-body {
  position: relative;
  height: 100%;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: var(--r-lg);
  background:
    linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(135deg,
      color-mix(in srgb, var(--accent) 24%, transparent),
      transparent 38%,
      color-mix(in srgb, var(--gold) 20%, transparent) 78%,
      color-mix(in srgb, var(--teal) 18%, transparent)) border-box;
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(10px) saturate(1.15);
  transition: box-shadow 0.35s var(--ease), transform 0.35s var(--ease);
}

.pad .gcard-body { padding: 24px 26px; }

/* 流光：只在 body 内裁切，不伤骑缝元素 */
.gcard-body::after {
  content: '';
  position: absolute;
  top: -60%;
  bottom: -60%;
  left: -30%;
  width: 34%;
  background: linear-gradient(100deg, transparent, color-mix(in srgb, #fff 30%, transparent), transparent);
  transform: skewX(-18deg) translateX(-160%);
  pointer-events: none;
}

.hover:hover .gcard-body {
  box-shadow: var(--shadow-2), var(--e-glow);
  transform: translateY(-2px);
}
.hover:hover .gcard-body::after {
  animation: gcard-shine 0.9s var(--ease) forwards;
}
@keyframes gcard-shine {
  to { transform: skewX(-18deg) translateX(640%); }
}
</style>
