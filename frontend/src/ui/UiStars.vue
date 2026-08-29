<script setup>
/**
 * 难度星级（v2 重做）：逐星填充，支持半星，彻底解决百分比裁切错位。
 * readonly 只读展示；交互模式点击设置 1-5。
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: 0 },
  readonly: { type: Boolean, default: false },
  size: { type: Number, default: 15 },
})

const emit = defineEmits(['update:modelValue'])

// 展示值取整到 0.5（AI 可能返回 3.5 之类的小数）
const display = computed(() => Math.round((Number(props.modelValue) || 0) * 2) / 2)

function fillFor(index) {
  // index: 0-4；返回该星填充比例 0 / 0.5 / 1
  const v = display.value - index
  return `${Math.min(1, Math.max(0, v)) * 100}%`
}

function pick(index) {
  if (props.readonly) return
  emit('update:modelValue', index + 1)
}
</script>

<template>
  <span class="stars" :class="{ readonly }" role="img" :aria-label="`难度 ${display} / 5`">
    <span
      v-for="(s, i) in 5"
      :key="i"
      class="star-slot"
      :class="{ interactive: !readonly }"
      :style="{ width: size + 'px', height: size + 'px' }"
      :title="readonly ? '' : `${i + 1} 星`"
      @click="pick(i)"
    >
      <svg class="star-bg" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-3-5.4 3 1.1-6L3.2 9.4l6.1-.8L12 3Z"/></svg>
      <span class="star-clip" :style="{ width: fillFor(i) }">
        <svg :width="size" :height="size" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-3-5.4 3 1.1-6L3.2 9.4l6.1-.8L12 3Z"/></svg>
      </span>
    </span>
  </span>
</template>

<style scoped>
.stars {
  display: inline-flex;
  gap: 2px;
  line-height: 0;
}
.star-slot {
  position: relative;
  display: inline-block;
}
.star-slot.interactive {
  cursor: pointer;
}
.star-slot.interactive:hover .star-bg {
  color: var(--gold);
}
.star-bg {
  display: block;
  color: var(--line-strong);
}
.star-clip {
  position: absolute;
  inset: 0 auto 0 0;
  overflow: hidden;
  pointer-events: none;
}
.star-clip svg {
  display: block;
  color: var(--gold);
}
</style>
