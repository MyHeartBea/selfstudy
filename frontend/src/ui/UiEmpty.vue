<script setup>
/** 空状态：可选印章（seal = 一个汉字），像"此册未启"盖的一方淡墨印 */
import Icon from './Icon.vue'

defineProps({
  text: { type: String, default: '暂无数据' },
  icon: { type: String, default: 'inbox' },
  /* 页面专属汉字印：错/式/知/词/卷/习… 传入时替代图标框 */
  seal: { type: String, default: '' },
})
</script>

<template>
  <div class="empty">
    <span v-if="seal" class="empty-seal serif" aria-hidden="true">{{ seal }}</span>
    <span v-else class="empty-icon"><Icon :name="icon" :size="26" /></span>
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
/* 汉字印章：微倾的淡墨方印，"空"也是一种状态而不是缺数据 */
.empty-seal {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  border: 1.5px solid color-mix(in srgb, var(--ink) 30%, transparent);
  color: var(--ink-2);
  font-size: 34px;
  font-weight: 900;
  line-height: 1;
  transform: rotate(-4deg);
  opacity: 0.55;
  box-shadow: inset 0 0 0 3px transparent;
}
.empty p {
  font-size: 13.5px;
}
</style>
