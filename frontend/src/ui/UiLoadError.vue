<script setup>
/**
 * 加载失败态。
 *
 * 它和 UiEmpty 必须是两个东西：请求失败时"有没有数据"其实未知，
 * 却会掉进 `v-else-if="!items.length"` 的「暂无数据」分支（拦截器只弹一条
 * 3 秒就消失的 toast），用户以为库是空的。这里把失败单独摆出来并给重试。
 */
import Icon from './Icon.vue'
import UiButton from './UiButton.vue'

defineProps({
  text: { type: String, default: '加载失败' },
  hint: { type: String, default: '' },
  retryText: { type: String, default: '重新加载' },
})
const emit = defineEmits(['retry'])
</script>

<template>
  <div class="load-error">
    <span class="le-icon"><Icon name="alert" :size="24" /></span>
    <p class="le-text">{{ text }}</p>
    <p v-if="hint" class="le-hint">{{ hint }}</p>
    <UiButton variant="primary" size="sm" @click="emit('retry')">
      <Icon name="refresh" :size="14" />
      {{ retryText }}
    </UiButton>
    <slot></slot>
  </div>
</template>

<style scoped>
.load-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 20px;
  text-align: center;
}
.le-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 18px;
  color: var(--accent);
  background: var(--accent-soft);
  border: 1px dashed var(--accent-ring);
}
.le-text {
  margin: 0;
  font-size: 13.5px;
  color: var(--ink-2);
}
.le-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-3);
}
</style>
