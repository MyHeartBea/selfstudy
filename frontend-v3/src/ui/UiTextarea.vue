<!--
  UiTextarea —— 多行文本
  ---------------------------------------------------------------------------
  与 UiField 同族：状态语义一致（空闲/聚焦/错误/禁用），标签与控件 id 关联，
  错误走 aria-invalid + aria-describedby。多行控件额外做两件事：
   - 自动增高（按内容撑开，最多到 maxRows 后转为滚动），避免小框子里看长题干
   - 等宽读数（字数）固定在右上角，不随内容跳动
-->
<script setup>
import { computed, onMounted, ref, useId, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  rows: { type: Number, default: 4 },
  /** 自动增高上限（超过后出现滚动条） */
  maxRows: { type: Number, default: 14 },
  disabled: { type: Boolean, default: false },
  showCount: { type: Boolean, default: false },
  maxLength: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue'])

const uid = useId()
const fieldId = computed(() => `t-${uid}`)
const descId = computed(() => `d-${uid}`)
const hasError = computed(() => !!props.error)
const el = ref(null)
const countText = computed(() =>
  props.maxLength
    ? `${props.modelValue.length} / ${props.maxLength}`
    : `${props.modelValue.length}`,
)

/** 自动增高：只改 height，不改宽（避免横向重排） */
function fit() {
  const node = el.value
  if (!node) return
  const cs = getComputedStyle(node)
  const line = parseFloat(cs.lineHeight) || 21
  const padY = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom)
  const max = line * props.maxRows + padY
  node.style.height = 'auto'
  node.style.height = Math.min(node.scrollHeight, max) + 'px'
  node.style.overflowY = node.scrollHeight > max ? 'auto' : 'hidden'
}

onMounted(fit)
watch(
  () => props.modelValue,
  () => requestAnimationFrame(fit),
)
</script>

<template>
  <div class="wrap">
    <div v-if="label || showCount" class="row">
      <label v-if="label" :for="fieldId">{{ label }}</label>
      <span v-if="showCount" class="count">{{ countText }}</span>
    </div>
    <textarea
      :id="fieldId"
      ref="el"
      class="ctrl"
      :value="modelValue"
      :rows="rows"
      :placeholder="placeholder"
      :disabled="disabled"
      :maxlength="maxLength || undefined"
      :aria-invalid="hasError ? 'true' : undefined"
      :aria-describedby="error || hint ? descId : undefined"
      @input="emit('update:modelValue', $event.target.value)"
    ></textarea>
    <p v-if="error" :id="descId" class="msg err">{{ error }}</p>
    <p v-else-if="hint" :id="descId" class="msg hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.wrap {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
.row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
label {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.count {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  color: var(--ink-3);
}
.ctrl {
  width: 100%;
  padding: 11px 13px;
  background: var(--sky-1);
  color: var(--ink-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font: inherit;
  font-size: var(--fs-body);
  line-height: 1.7;
  resize: none;
  transition:
    border-color 0.25s var(--e-settle),
    background 0.25s var(--e-settle);
}
.ctrl::placeholder {
  color: var(--ink-3);
}
.ctrl:hover:not(:disabled) {
  border-color: var(--ink-3);
}
.ctrl:focus {
  outline: none;
  border-color: var(--redshift);
  background: var(--sky-2);
}
.ctrl:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ctrl[aria-invalid='true'] {
  border-color: var(--redshift);
}
.msg {
  font-size: 12px;
  line-height: 1.6;
}
.msg.err {
  color: var(--redshift);
}
.msg.hint {
  color: var(--ink-2);
}
</style>
