<script setup>
/**
 * 难度星级（v2 重做）：逐星填充，支持半星，彻底解决百分比裁切错位。
 * readonly 只读展示；交互模式是可键盘操作的 radiogroup（方向键改分、Home/End 到端点）。
 */
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Number, default: 0 },
  readonly: { type: Boolean, default: false },
  size: { type: Number, default: 15 },
})

const emit = defineEmits(['update:modelValue'])

// 展示值取整到 0.5（AI 可能返回 3.5 之类的小数）
const display = computed(() => Math.round((Number(props.modelValue) || 0) * 2) / 2)

function fillFor(index) {
  // index: 0-4；返回该星填充比例 0 / 0.5 / 1
  const v = display.value - index
  return `${Math.min(1, Math.max(0, v)) * 100}%`
}

const slots = ref([])
function setSlot(el, i) {
  if (el) slots.value[i] = el
}

// 焦点跟随：键盘操作后要把焦点挪到新选中的那颗星上（roving tabindex）。
// 未选中（0 星）时落在第 1 颗，保证组内始终有一个 Tab 落点。
const cursor = ref(-1)
const tabTarget = computed(() => {
  if (cursor.value >= 0) return cursor.value
  return Math.min(4, Math.max(0, Math.round(display.value) - 1))
})

function pick(index) {
  if (props.readonly) return
  const i = Math.min(4, Math.max(0, index))
  cursor.value = i
  emit('update:modelValue', i + 1)
}

function focusSlot(i) {
  nextTick(() => slots.value[i]?.focus())
}

function onKey(event, index) {
  if (props.readonly) return
  const k = event.key
  if (k === 'ArrowRight' || k === 'ArrowUp') {
    event.preventDefault()
    const i = Math.min(4, index + 1)
    pick(i)
    focusSlot(i)
  } else if (k === 'ArrowLeft' || k === 'ArrowDown') {
    event.preventDefault()
    const i = Math.max(0, index - 1)
    pick(i)
    focusSlot(i)
  } else if (k === 'Home') {
    event.preventDefault()
    pick(0)
    focusSlot(0)
  } else if (k === 'End') {
    event.preventDefault()
    pick(4)
    focusSlot(4)
  } else if (k === 'Enter' || k === ' ' || k === 'Spacebar') {
    event.preventDefault()
    pick(index)
  }
}
</script>

<template>
  <span
    class="stars"
    :class="{ readonly }"
    :role="readonly ? 'img' : 'radiogroup'"
    :aria-label="`难度 ${display} / 5`"
  >
    <span
      v-for="(s, i) in 5"
      :key="i"
      :ref="(el) => setSlot(el, i)"
      class="star-slot"
      :class="{ interactive: !readonly }"
      :role="readonly ? undefined : 'radio'"
      :aria-checked="readonly ? undefined : display === i + 1"
      :aria-label="readonly ? undefined : `${i + 1} 星`"
      :tabindex="readonly ? undefined : tabTarget === i ? 0 : -1"
      :style="{ width: size + 'px', height: size + 'px' }"
      :title="readonly ? '' : `${i + 1} 星`"
      @click="pick(i)"
      @keydown="onKey($event, i)"
    >
      <svg
        class="star-bg"
        aria-hidden="true"
        :width="size"
        :height="size"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      >
        <path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-3-5.4 3 1.1-6L3.2 9.4l6.1-.8L12 3Z" />
      </svg>
      <span class="star-clip" :style="{ width: fillFor(i) }">
        <svg
          aria-hidden="true"
          :width="size"
          :height="size"
          viewBox="0 0 24 24"
          fill="currentColor"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linejoin="round"
        >
          <path d="m12 3 2.7 5.6 6.1.8-4.5 4.3 1.1 6-5.4-3-5.4 3 1.1-6L3.2 9.4l6.1-.8L12 3Z" />
        </svg>
      </span>
    </span>
  </span>
</template>

<style scoped>
.stars {
  display: inline-flex;
  gap: 2px;
  line-height: 0;
}
.star-slot {
  position: relative;
  display: inline-block;
}
.star-slot.interactive {
  cursor: pointer;
}
.star-slot.interactive:hover .star-bg {
  color: var(--gold);
}
.star-slot:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
.star-bg {
  display: block;
  color: var(--line-strong);
}
.star-clip {
  position: absolute;
  inset: 0 auto 0 0;
  overflow: hidden;
  pointer-events: none;
}
.star-clip svg {
  display: block;
  color: var(--gold);
}
</style>
