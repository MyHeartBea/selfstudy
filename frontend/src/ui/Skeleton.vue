<script setup>
/**
 * 骨架屏：墨色微光扫过。variant = text | rect | circle；
 * 也可用 count + 换行模拟多行文本。
 */
defineProps({
  variant: { type: String, default: 'rect' },
  width: { type: [Number, String], default: '100%' },
  height: { type: Number, default: 14 },
  radius: { type: Number, default: 8 },
  count: { type: Number, default: 1 },
})
</script>

<template>
  <span class="skeleton-group" aria-hidden="true">
    <span
      v-for="i in count"
      :key="i"
      class="skeleton"
      :class="`sk-${variant}`"
      :style="{
        width: variant === 'circle' ? height + 'px' : typeof width === 'number' ? width + 'px' : width,
        height: height + 'px',
        borderRadius: variant === 'circle' ? '50%' : radius + 'px',
      }"
    ></span>
  </span>
</template>

<style scoped>
.skeleton-group { display: inline-flex; flex-direction: column; gap: 8px; }
.skeleton {
  position: relative;
  display: inline-block;
  overflow: hidden;
  background: var(--surface-2);
}
.skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--ink) 7%, transparent), transparent);
  animation: sk-sweep 1.4s ease-in-out infinite;
}
@keyframes sk-sweep { to { transform: translateX(100%); } }
.sk-text { height: 14px !important; }
</style>
