<!--
  InkDot —— 掌握度墨点（五档）
  ---------------------------------------------------------------------------
  语义：**墨色的浓淡 = 掌握的深浅**。这是全站"未掌握是暗、已掌握是光"最直接的体现，
  也是从 v2 沿用下来的一个真正好用的表达（比进度条更能表达"模糊地带"）。

  为什么用 5 档而不是百分比：复习自评本身只有三档（会 / 模糊 / 不会），
  显示成 5 档是"累积沉淀"的结果，比精确百分比更诚实 —— 不做假精度。

  可访问：整体给一个 role="img" + aria-label（屏幕阅读器读"掌握度 3 / 5"），
  内部圆点对辅助技术隐藏。
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** 当前档位 0-5（0 表示完全未掌握） */
  value: { type: Number, default: 0 },
  max: { type: Number, default: 5 },
  size: { type: String, default: 'md' },
  label: { type: String, default: '掌握度' },
})

const dots = computed(() => {
  const v = Math.max(0, Math.min(props.max, Math.round(props.value)))
  return Array.from({ length: props.max }, (_, i) => i < v)
})
const aria = computed(
  () => `${props.label} ${Math.max(0, Math.min(props.max, props.value))} / ${props.max}`,
)
</script>

<template>
  <span class="ink-dot" :class="`s-${size}`" role="img" :aria-label="aria">
    <i v-for="(on, i) in dots" :key="i" :class="{ on }" aria-hidden="true"></i>
  </span>
</template>

<style scoped>
.ink-dot {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ink-dot i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--line-strong);
  transition:
    background 0.3s var(--e-settle),
    box-shadow 0.3s var(--e-settle);
}
/* 有墨的点：亮度随档位递进（越靠右越亮），形成"沉淀"的视觉 */
.ink-dot i.on {
  background: var(--ink-0);
  box-shadow: none;
}
.ink-dot i.on:nth-child(1) {
  opacity: 0.5;
}
.ink-dot i.on:nth-child(2) {
  opacity: 0.66;
}
.ink-dot i.on:nth-child(3) {
  opacity: 0.8;
}
.ink-dot i.on:nth-child(4) {
  opacity: 0.92;
}
.ink-dot i.on:nth-child(5) {
  opacity: 1;
}

.s-sm i {
  width: 7px;
  height: 7px;
}
.s-lg i {
  width: 12px;
  height: 12px;
}
</style>
