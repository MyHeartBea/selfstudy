<script setup>
/**
 * 彩色小标签：color 缺省时用中性样式；soft=true 时用浅底深字。
 */
import { computed } from 'vue'

const props = defineProps({
  color: { type: String, default: '' },
  soft: { type: Boolean, default: false },
  size: { type: String, default: 'md' },
  clickable: { type: Boolean, default: false },
})

const style = computed(() => {
  if (!props.color) return {}
  return props.soft
    ? { background: `color-mix(in srgb, ${props.color} 13%, transparent)`, color: props.color, borderColor: `color-mix(in srgb, ${props.color} 26%, transparent)` }
    : { background: props.color, color: '#fff', borderColor: 'transparent' }
})
</script>

<template>
  <span class="ui-tag" :class="[`tag-${size}`, { clickable }]" :style="style">
    <slot></slot>
  </span>
</template>

<style scoped>
.ui-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tag-sm { padding: 1px 7px; font-size: 11px; }
.clickable { cursor: pointer; transition: filter 0.15s, border-color 0.15s; }
.clickable:hover { filter: brightness(0.96); border-color: var(--accent); }
</style>
