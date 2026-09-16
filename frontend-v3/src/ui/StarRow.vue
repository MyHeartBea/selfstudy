<!--
  StarRow —— 星等（复习次数 / 亮度）
  ---------------------------------------------------------------------------
  语义：**复习一次亮一分**。用于"这道题被复习过几次"，与掌握度（InkDot）区分开：
   - InkDot  回答"记住多少"（主观、有模糊地带）
   - StarRow 回答"看过几遍"（客观、可数）
   - 用 SVG 星形（Lucide 的 star 路径），不用 Unicode 星号 —— 全站禁止字符图标。
   亮星与暗星共用同一路径，只改 fill / opacity，保证形状完全一致（不抖）。
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  max: { type: Number, default: 7 },
  size: { type: Number, default: 12 },
  label: { type: String, default: '复习遍数' },
})

/** Lucide star 的路径（24x24 视图框），与库中形状一致 */
const STAR_PATH =
  'M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z'

const stars = computed(() => {
  const v = Math.max(0, Math.min(props.max, Math.round(props.value)))
  return Array.from({ length: props.max }, (_, i) => i < v)
})
const aria = computed(
  () => `${props.label} ${Math.max(0, Math.min(props.max, props.value))} / ${props.max}`,
)
</script>

<template>
  <span class="star-row" role="img" :aria-label="aria">
    <svg
      v-for="(on, i) in stars"
      :key="i"
      class="star"
      :class="{ on }"
      :width="size"
      :height="size"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path :d="STAR_PATH" />
    </svg>
  </span>
</template>

<style scoped>
.star-row {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--ink-3);
}
.star {
  fill: none;
  stroke: currentColor;
  opacity: 0.55;
}
/* 亮星：红移填充（反复复习过的题就是这个色，与"红移星"隐喻一致） */
.star.on {
  color: var(--redshift);
  fill: var(--redshift);
  opacity: 1;
  filter: drop-shadow(0 0 4px oklch(0.665 0.196 34 / 0.45));
}
@media (prefers-reduced-motion: reduce) {
  .star {
    transition: none;
  }
}
</style>
