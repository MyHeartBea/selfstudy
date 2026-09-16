<!--
  UiField —— 单行文本输入
  ---------------------------------------------------------------------------
  约定（全站表单控件统一）：
  - 标签与控件通过 id 关联（点标签可聚焦，屏幕阅读器可读）
  - 错误用 aria-invalid + aria-describedby 关联提示文本，不只是变红
  - focus 用边框转红移色（全站三道同心环留给非输入类焦点目标，避免双重描边）
  - 过渡只改 border-color / background，不改尺寸（避免聚焦时抖动）
-->
<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  type: { type: String, default: 'text' },
  disabled: { type: Boolean, default: false },
  /** 右上角等宽读数（例如 "12 / 80"），强化仪器感 */
  counter: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'enter'])

const uid = useId()
const fieldId = computed(() => `f-${uid}`)
const descId = computed(() => `d-${uid}`)
const hasError = computed(() => !!props.error)
</script>

<template>
  <div class="wrap">
    <div v-if="label || counter" class="row">
      <label v-if="label" :for="fieldId">{{ label }}</label>
      <span v-if="counter" class="count">{{ counter }}</span>
    </div>
    <input
      :id="fieldId"
      class="ctrl"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :aria-invalid="hasError ? 'true' : undefined"
      :aria-describedby="error || hint ? descId : undefined"
      @input="emit('update:modelValue', $event.target.value)"
      @keydown.enter="emit('enter', $event)"
    />
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
