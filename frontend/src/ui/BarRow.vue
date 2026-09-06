<script setup>
/**
 * 条形行：标签 + 圆角条 + 数值。挂载后宽度从 0 生长到目标值。
 * labelWidth 固定标签列宽，弱项列表等多行对齐场景用。
 */
import { onMounted, ref } from 'vue'

const props = defineProps({
  label: { type: String, default: '' },
  percentage: { type: Number, default: 0 }, // 0-100
  value: { type: [String, Number], default: '' },
  color: { type: String, default: 'var(--accent)' },
  labelWidth: { type: Number, default: 0 }, // 0 = 自适应
  barHeight: { type: Number, default: 9 },
})

const shown = ref(false)

onMounted(() => {
  requestAnimationFrame(() => {
    setTimeout(() => {
      shown.value = true
    }, 120)
  })
})
</script>

<template>
  <div class="brow">
    <span v-if="label" class="b-label" :style="labelWidth ? { width: labelWidth + 'px' } : null">{{ label }}</span>
    <div class="b-bar" :style="{ height: barHeight + 'px' }">
      <div class="b-fill" :style="{ width: (shown ? Math.min(100, Math.max(0, percentage)) : 0) + '%', background: color }"></div>
    </div>
    <span v-if="value !== ''" class="b-val num">{{ value }}</span>
  </div>
</template>

<style scoped>
.brow {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.b-label {
  font-size: 13px;
  color: var(--ink-2);
  flex: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.b-bar {
  flex: 1;
  border-radius: 99px;
  background: var(--surface-2);
  overflow: hidden;
  min-width: 0;
}
.b-fill {
  height: 100%;
  border-radius: 99px;
  transition: width 1.1s var(--spring);
}
.b-val {
  width: 34px;
  text-align: right;
  font-size: 12.5px;
  color: var(--ink-3);
  flex: none;
}
</style>
