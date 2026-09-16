<!--
  UiTag —— 语义标签（星等标记）
  ---------------------------------------------------------------------------
  与 v2 的印章标签不同：这里用**极细描边 + 等宽小字**，靠色彩语义区分，不靠填充色块
  （暗底上大面积填充会互相打架）。四种 tone 与设计令牌的语义色一一对应：
    red-shift（红移，错误/反复错） · vein（数据/进行中） · gold（警示/过载） · ink（中性）
  可选 dot：左侧一个小圆点，用于"状态"而不是"分类"（状态需要更强的即时识别）。
-->
<script setup>
defineProps({
  tone: { type: String, default: 'ink' },
  size: { type: String, default: 'md' },
  dot: { type: Boolean, default: false },
})
</script>

<template>
  <span class="tag" :class="[`t-${tone}`, `s-${size}`]">
    <i v-if="dot" class="dot" aria-hidden="true"></i>
    <slot />
  </span>
</template>

<style scoped>
.tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  line-height: 1.6;
  white-space: nowrap;
}
.s-sm {
  padding: 1px 7px;
  font-size: 10px;
}
.s-lg {
  padding: 5px 12px;
  font-size: var(--fs-mono-lg);
}
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
}

.t-red-shift {
  color: var(--redshift);
  background: oklch(0.665 0.196 34 / 0.08);
}
.t-vein {
  color: var(--vein);
  background: oklch(0.775 0.098 200 / 0.08);
}
.t-gold {
  color: var(--gold);
  background: oklch(0.775 0.12 85 / 0.08);
}
.t-violet {
  color: var(--violet);
  background: oklch(0.685 0.145 285 / 0.08);
}
.t-ink {
  color: var(--ink-2);
}
</style>
