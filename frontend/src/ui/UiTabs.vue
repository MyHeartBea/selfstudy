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
  gap: 4px;
  padding: 4px;
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.seg-tab {
  padding: 7px 16px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.seg-tab:hover { color: var(--ink); }
.seg-tab.active {
  background: var(--surface);
  color: var(--ink);
  box-shadow: var(--shadow-1);
  border: 1px solid var(--line);
}
</style>
