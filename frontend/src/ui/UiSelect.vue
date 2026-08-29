<script setup>
/** 下拉选择：options=[{label,value}] 或字符串数组；支持 clearable / disabled / 无边框紧凑模式。 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  modelValue: { type: [String, Number, null], default: null },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' },
  clearable: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'change'])

const open = ref(false)
const root = ref(null)

const normalized = computed(() =>
  props.options.map((item) =>
    typeof item === 'object' ? item : { label: String(item), value: item },
  ),
)

const current = computed(() =>
  normalized.value.find((item) => item.value === props.modelValue) || null,
)

function pick(option) {
  emit('update:modelValue', option.value)
  emit('change', option.value)
  open.value = false
}

function clear(event) {
  event.stopPropagation()
  emit('update:modelValue', null)
  emit('change', null)
}

function onDocClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onUnmounted(() => document.removeEventListener('mousedown', onDocClick))
</script>

<template>
  <div ref="root" class="select" :class="{ open, disabled, compact }">
    <button type="button" class="select-trigger" :disabled="disabled" @click="!disabled && (open = !open)">
      <span v-if="current" class="select-label">{{ current.label }}</span>
      <span v-else class="select-placeholder">{{ placeholder }}</span>
      <span v-if="clearable && current" class="select-clear" role="button" aria-label="清空" @click.stop="clear">
        <Icon name="x" :size="13" />
      </span>
      <Icon v-else name="chevron-down" :size="14" class="select-arrow" />
    </button>
    <Transition name="drop">
      <div v-if="open" class="select-menu" role="listbox">
        <button
          v-for="option in normalized"
          :key="option.value"
          type="button"
          class="select-option"
          :class="{ active: option.value === modelValue }"
          role="option"
          :aria-selected="option.value === modelValue"
          @click="pick(option)"
        >
          <span>{{ option.label }}</span>
          <Icon v-if="option.value === modelValue" name="check" :size="14" />
        </button>
        <div v-if="!normalized.length" class="select-empty">暂无选项</div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.select {
  position: relative;
  display: inline-block;
  min-width: 120px;
}

.select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 36px;
  padding: 0 12px;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 10px;
  font-size: 13.5px;
  color: var(--ink);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.select-trigger:hover:not(:disabled) { border-color: var(--accent); }
.select.open .select-trigger {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.select-trigger:disabled { opacity: 0.5; cursor: not-allowed; }

.select.compact .select-trigger {
  height: 30px;
  padding: 0 10px;
  font-size: 12.5px;
  border-radius: 8px;
}

.select-placeholder { color: var(--ink-3); }
.select-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.select-clear {
  display: inline-flex;
  padding: 2px;
  border-radius: 5px;
  color: var(--ink-3);
}
.select-clear:hover { color: var(--red); background: var(--red-soft); }

.select-arrow { color: var(--ink-3); transition: transform 0.15s; }
.select.open .select-arrow { transform: rotate(180deg); }

.select-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 60;
  min-width: 100%;
  max-height: 280px;
  overflow-y: auto;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--shadow-2);
  padding: 5px;
}

.select-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}
.select-option:hover { background: var(--surface-2); }
.select-option.active { color: var(--accent-ink); font-weight: 600; background: var(--accent-soft); }

.select-empty {
  padding: 12px;
  text-align: center;
  color: var(--ink-3);
  font-size: 12.5px;
}

.drop-enter-active, .drop-leave-active { transition: opacity 0.14s, transform 0.14s; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
