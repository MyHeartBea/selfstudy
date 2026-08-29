<script setup>
/** 复选框 */
defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <label class="checkbox">
    <input
      type="checkbox"
      :checked="modelValue"
      @change="$emit('update:modelValue', $event.target.checked)"
    />
    <span class="box" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 12.5 5 5L20 6.5"/></svg>
    </span>
    <span v-if="label" class="text">{{ label }}</span>
  </label>
</template>

<style scoped>
.checkbox {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  user-select: none;
  font-size: 13px;
  color: var(--ink-2);
}
.checkbox input { position: absolute; opacity: 0; pointer-events: none; }
.box {
  width: 17px;
  height: 17px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--line-strong);
  border-radius: 5.5px;
  background: var(--surface);
  transition: all 0.13s;
}
.checkbox input:checked + .box {
  background: var(--accent);
  border-color: var(--accent);
}
.checkbox input:focus-visible + .box {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.text { line-height: 1; }
</style>
