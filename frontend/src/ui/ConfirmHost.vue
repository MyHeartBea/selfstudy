<script setup>
/** 全局确认弹窗宿主：配合 ui/confirm.js 的 confirmDialog 使用，挂在 App.vue 根部。 */
import { nextTick, watch } from 'vue'
import UiModal from './UiModal.vue'
import UiButton from './UiButton.vue'
import Icon from './Icon.vue'
import { confirmState, confirmCancel, confirmOk } from './confirm'

watch(
  () => confirmState.open,
  async (open) => {
    if (open && confirmState.input) {
      await nextTick()
      document.querySelector('.confirm-input')?.focus()
    }
  },
)
</script>

<template>
  <UiModal :model-value="confirmState.open" :title="confirmState.title" size="sm" @update:model-value="confirmCancel()">
    <p class="confirm-msg">{{ confirmState.message }}</p>
    <input
      v-if="confirmState.input"
      v-model="confirmState.inputValue"
      class="field-input confirm-input"
      :placeholder="confirmState.input.placeholder || ''"
      @keyup.enter="confirmOk"
    />
    <p v-if="confirmState.error" class="confirm-error">{{ confirmState.error }}</p>
    <template #footer>
      <UiButton variant="ghost" @click="confirmCancel">取消</UiButton>
      <UiButton :variant="confirmState.danger ? 'primary' : 'primary'" @click="confirmOk">
        <Icon v-if="confirmState.danger" name="trash" :size="15" />
        {{ confirmState.confirmText }}
      </UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.confirm-msg {
  margin: 0;
  color: var(--ink-2);
  font-size: 13.5px;
}
.confirm-error {
  margin: 8px 0 0;
  color: var(--red);
  font-size: 12.5px;
}
</style>
