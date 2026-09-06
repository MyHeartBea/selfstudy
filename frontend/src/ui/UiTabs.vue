<script setup>
/** 分段选项卡：v-model 绑定 name。 */
defineProps({
  tabs: { type: Array, default: () => [] }, // [{name,label}]
  modelValue: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="seg-tabs" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.name"
      type="button"
      class="seg-tab"
      :class="{ active: tab.name === modelValue }"
      role="tab"
      :aria-selected="tab.name === modelValue"
      @click="$emit('update:modelValue', tab.name)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.seg-tabs {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  background: var(--surface-2);
  border-radius: 11px;
}

.seg-tab {
  padding: 6px 15px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--ink-3);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s var(--ease);
  white-space: nowrap;
}
.seg-tab:hover { color: var(--ink); }
.seg-tab.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-1);
}
</style>
