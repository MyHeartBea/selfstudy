<script setup>
/** 细进度条 */
import { computed } from 'vue'

const props = defineProps({
  percentage: { type: Number, default: 0 },
  color: { type: String, default: 'var(--accent)' },
  height: { type: Number, default: 8 },
})

const width = computed(() => `${Math.min(100, Math.max(0, props.percentage))}%`)
</script>

<template>
  <div class="progress" :style="{ height: height + 'px' }">
    <div class="progress-inner" :style="{ width, background: color }"></div>
  </div>
</template>

<style scoped>
.progress {
  width: 100%;
  background: var(--surface-2);
  border-radius: 999px;
  overflow: hidden;
}
.progress-inner {
  height: 100%;
  border-radius: 999px;
  transition: width 0.9s var(--spring);
}
</style>
