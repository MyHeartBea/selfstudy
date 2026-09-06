<script setup>
/** 下拉菜单（触发按钮 + 菜单列表）：items=[{label,command}] */
import { onMounted, onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'

defineProps({
  items: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  variant: { type: String, default: 'outline' },
  size: { type: String, default: 'md' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['command'])

const open = ref(false)
const root = ref(null)

function onCommand(item) {
  open.value = false
  emit('command', item.command)
}

function onDocClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onUnmounted(() => document.removeEventListener('mousedown', onDocClick))
</script>

<template>
  <div ref="root" class="dropdown">
    <slot name="trigger" :open="open" :toggle="() => (open = !open)">
      <button type="button" class="dd-trigger" :disabled="disabled" @click="open = !open">
        <slot></slot>
        <span v-if="label">{{ label }}</span>
        <Icon name="chevron-down" :size="13" class="dd-arrow" :class="{ up: open }" />
      </button>
    </slot>
    <Transition name="drop">
      <div v-if="open" class="dropdown-menu">
        <button v-for="item in items" :key="item.command" type="button" class="dropdown-item" @click="onCommand(item)">
          <Icon v-if="item.icon" :name="item.icon" :size="14" />
          <span>{{ item.label }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dropdown { position: relative; display: inline-block; }

/* 默认触发器：与 UiButton outline 同一视觉（此前裸用 .btn 全局类导致样式脱落） */
.dd-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  background: var(--surface);
  color: var(--ink);
  font-family: inherit;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  transition: border-color 0.15s var(--ease), color 0.15s var(--ease), background 0.15s var(--ease), box-shadow 0.2s var(--ease), transform 0.25s var(--spring);
}
.dd-trigger:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-ink);
  background: var(--accent-soft);
  box-shadow: var(--e-glow);
}
.dd-trigger:active:not(:disabled) { transform: translateY(1px) scale(0.985); }
.dd-trigger:disabled { opacity: 0.5; cursor: not-allowed; }
.dd-trigger svg { flex: none; }
.dd-arrow { color: var(--ink-3); transition: transform 0.2s var(--ease); }
.dd-arrow.up { transform: rotate(180deg); }
.dropdown:hover .dd-arrow { color: var(--accent-ink); }

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 60;
  min-width: 150px;
  background: linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box;
  border: 1px solid transparent;
  border-radius: 13px;
  box-shadow: var(--shadow-3);
  backdrop-filter: blur(16px) saturate(1.2);
  padding: 5px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 11px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.14s var(--ease);
}
.dropdown-item:hover { background: var(--surface-2); }

.drop-enter-active, .drop-leave-active { transition: opacity 0.18s var(--ease), transform 0.22s var(--spring); }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px) scale(0.98); }
</style>
