<!--
  UiSelect —— 下拉选择
  ---------------------------------------------------------------------------
  刻意用**原生 <select>**：自定义下拉会重新实现键盘导航、Tab 顺序、移动端选择器、
  屏幕阅读器语义 —— 这些原生已经做对了，重造只会更容易出错。
  这里只做视觉接管（外观、箭头、聚焦），行为完全交给浏览器。

  箭头用 SVG（Lucide 的 chevron-down 路径），不用字符箭头 —— 全站禁用字符图标。
-->
<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, null], default: '' },
  options: { type: Array, default: () => [] }, // [{ value, label, disabled? }]
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const uid = useId()
const fieldId = computed(() => `s-${uid}`)
const descId = computed(() => `d-${uid}`)
const hasError = computed(() => !!props.error)

/** Lucide chevron-down */
const CHEVRON = 'm6 9 6 6 6-6'
</script>

<template>
  <div class="wrap">
    <div v-if="label" class="row">
      <label :for="fieldId">{{ label }}</label>
    </div>
    <div class="box" :class="{ err: hasError, dis: disabled }">
      <select
        :id="fieldId"
        class="ctrl"
        :value="modelValue"
        :disabled="disabled"
        :aria-invalid="hasError ? 'true' : undefined"
        :aria-describedby="error || hint ? descId : undefined"
        @change="emit('update:modelValue', $event.target.value)"
      >
        <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
        <option v-for="o in options" :key="o.value" :value="o.value" :disabled="o.disabled">
          {{ o.label }}
        </option>
      </select>
      <svg
        class="chev"
        viewBox="0 0 24 24"
        width="15"
        height="15"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path :d="CHEVRON" />
      </svg>
    </div>
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
label {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.box {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--sky-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  transition:
    border-color 0.25s var(--e-settle),
    background 0.25s var(--e-settle);
}
.box:hover:not(.dis) {
  border-color: var(--ink-3);
}
.box:focus-within {
  border-color: var(--redshift);
  background: var(--sky-2);
}
.box.err {
  border-color: var(--redshift);
}
.box.dis {
  opacity: 0.5;
}
.ctrl {
  appearance: none;
  width: 100%;
  padding: 11px 34px 11px 13px;
  background: transparent;
  color: var(--ink-0);
  border: 0;
  font: inherit;
  font-size: var(--fs-body);
  cursor: pointer;
}
.ctrl:disabled {
  cursor: not-allowed;
}
.ctrl:focus {
  outline: none;
}
/* option 在原生弹层里渲染，必须显式给深色底，否则部分浏览器会白底白字 */
.ctrl option {
  background: var(--sky-1);
  color: var(--ink-0);
}
.chev {
  position: absolute;
  right: 12px;
  color: var(--ink-2);
  pointer-events: none;
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
