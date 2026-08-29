<script setup>
/** 模态框：teleport 到 body，Esc 关闭、滚动锁定、宽档 size = sm | md | lg | xl */
import { onUnmounted, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: 'md' },
  closeOnEsc: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue'])

const WIDTH = { sm: '460px', md: '640px', lg: '820px', xl: '960px' }

function close() {
  emit('update:modelValue', false)
}

function onKeydown(event) {
  if (event.key === 'Escape' && props.closeOnEsc && props.modelValue) {
    event.stopPropagation()
    close()
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown, true)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', onKeydown, true)
      document.body.style.overflow = ''
    }
  },
)

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown, true)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modelValue" class="modal-backdrop" @mousedown.self="close()">
        <div class="modal-panel" :style="{ maxWidth: WIDTH[size] || WIDTH.md }" role="dialog" aria-modal="true">
          <header class="modal-head">
            <h3 class="modal-title">{{ title }}</h3>
            <button class="modal-close" aria-label="关闭" @click="close">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </header>
          <div class="modal-body">
            <slot></slot>
          </div>
          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer"></slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 6vh 16px 16px;
  background: color-mix(in srgb, var(--bg) 45%, rgba(20, 16, 12, 0.45));
  backdrop-filter: blur(3px);
  overflow-y: auto;
}

.modal-panel {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-3);
  display: flex;
  flex-direction: column;
  max-height: 88vh;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--line);
  flex: none;
}

.modal-title {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
}

.modal-close {
  display: inline-flex;
  padding: 6px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
}
.modal-close:hover { background: var(--surface-2); color: var(--ink); }

.modal-body {
  padding: 18px 20px;
  overflow-y: auto;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--line);
  flex: none;
}

.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-active .modal-panel, .modal-leave-active .modal-panel { transition: transform 0.22s cubic-bezier(0.22, 0.8, 0.36, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-panel, .modal-leave-to .modal-panel { transform: translateY(14px) scale(0.985); }
</style>
