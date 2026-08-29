<script setup>
/** 标签输入器：回车添加、失焦收尾、点 × 移除 */
import { ref } from 'vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: '输入后按回车添加' },
  color: { type: String, default: '' },
  suggestions: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const input = ref('')
const listId = `tag-list-${Math.random().toString(36).slice(2, 9)}`

function add() {
  const tag = input.value.trim()
  if (tag && !props.modelValue.includes(tag)) {
    emit('update:modelValue', [...props.modelValue, tag])
  }
  input.value = ''
}

function flush() {
  if (input.value.trim()) add()
}

function remove(tag) {
  emit('update:modelValue', props.modelValue.filter((item) => item !== tag))
}
</script>

<template>
  <div class="tag-editor">
    <span v-for="tag in modelValue" :key="tag" class="tag-chip" :style="color ? { background: color + '1a', color, borderColor: color + '40' } : {}">
      {{ tag }}
      <button type="button" class="chip-x" :aria-label="`移除 ${tag}`" @click="remove(tag)">
        <Icon name="x" :size="11" />
      </button>
    </span>
    <input
      v-model="input"
      class="tag-input"
      :placeholder="placeholder"
      :list="suggestions.length ? listId : undefined"
      @keydown.enter.prevent="add"
      @blur="flush"
    />
    <datalist v-if="suggestions.length" :id="listId">
      <option v-for="s in suggestions" :key="s" :value="s"></option>
    </datalist>
  </div>
</template>

<style scoped>
.tag-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  width: 100%;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px 3px 10px;
  border-radius: 999px;
  background: var(--bg-soft);
  border: 1px solid var(--line-strong);
  color: var(--ink);
  font-size: 12.5px;
  font-weight: 600;
  white-space: nowrap;
}

.chip-x {
  display: inline-flex;
  padding: 2px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
}
.chip-x:hover { color: var(--red); background: var(--red-soft); }

.tag-input {
  flex: 1;
  min-width: 140px;
  height: 30px;
  padding: 0 4px;
  border: none;
  background: transparent;
  font-size: 13px;
  outline: none;
  color: var(--ink);
}
.tag-input::placeholder { color: var(--ink-3); }
</style>
