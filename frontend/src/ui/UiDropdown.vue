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
      <button type="button" class="btn" :class="[`btn-${variant}`, `btn-${size}`]" :disabled="disabled" @click="open = !open">
        <slot></slot>
        <span v-if="label">{{ label }}</span>
        <Icon name="chevron-down" :size="13" />
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

.dropdown-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 60;
  min-width: 150px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--shadow-2);
  padding: 5px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 11px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}
.dropdown-item:hover { background: var(--surface-2); }

.drop-enter-active, .drop-leave-active { transition: opacity 0.14s, transform 0.14s; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
