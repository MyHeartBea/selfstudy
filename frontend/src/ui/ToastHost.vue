<script setup>
/** toast 容器：固定在顶部居中，自动消散。 */
import { toasts, dismiss } from './toast'
import Icon from './Icon.vue'

const ICON_MAP = {
  success: 'check',
  error: 'alert',
  warning: 'alert',
  info: 'sparkles',
}
</script>

<template>
  <Teleport to="body">
    <TransitionGroup name="toast" tag="div" class="toast-host" aria-live="polite">
      <div v-for="item in toasts" :key="item.id" class="toast" :class="`toast-${item.type}`" role="status">
        <Icon :name="ICON_MAP[item.type]" :size="16" />
        <span class="toast-msg">{{ item.message }}</span>
        <button class="toast-close" aria-label="关闭提示" @click="dismiss(item.id)">
          <Icon name="x" :size="13" />
        </button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1200;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: min(520px, calc(100vw - 32px));
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 11px 14px;
  border-radius: var(--r-md);
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-3);
  font-size: 13.5px;
}

.toast > :first-child {
  flex: none;
}

.toast-success { border-left: 3px solid var(--green); color: var(--green); }
.toast-error { border-left: 3px solid var(--red); color: var(--red); }
.toast-warning { border-left: 3px solid var(--gold); color: var(--gold); }
.toast-info { border-left: 3px solid var(--blue); color: var(--blue); }

.toast-msg {
  flex: 1;
  color: var(--ink);
}

.toast-close {
  flex: none;
  display: inline-flex;
  border: none;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  padding: 3px;
  border-radius: 6px;
}
.toast-close:hover { color: var(--ink); background: var(--surface-2); }

.toast-enter-active, .toast-leave-active { transition: all 0.28s cubic-bezier(0.22, 0.8, 0.36, 1); }
.toast-enter-from { opacity: 0; transform: translateY(-12px) scale(0.97); }
.toast-leave-to { opacity: 0; transform: translateY(-8px) scale(0.97); }
</style>
