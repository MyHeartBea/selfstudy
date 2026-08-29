<script setup>
/** 空状态 */
import Icon from './Icon.vue'

defineProps({
  text: { type: String, default: '暂无数据' },
  icon: { type: String, default: 'inbox' },
})
</script>

<template>
  <div class="empty">
    <span class="empty-icon"><Icon :name="icon" :size="26" /></span>
    <p>{{ text }}</p>
    <slot></slot>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 48px 20px;
  color: var(--ink-3);
  text-align: center;
}
.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  background: var(--surface-2);
  border: 1px dashed var(--line-strong);
}
.empty p { font-size: 13.5px; }
</style>
