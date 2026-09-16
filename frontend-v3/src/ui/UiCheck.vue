<!--
  UiCheck —— 勾选（星标式）
  ---------------------------------------------------------------------------
  原生 input[type=checkbox] + 视觉接管：用 opacity:0 覆盖而不是 display:none，
  这样键盘可聚焦、屏幕阅读器可读、focus-visible 可用（display:none 的 input 不可聚焦）。

  选中态用**实心方块 + 勾**（不是圆点）：与全站 2px 直角、仪器感一致。
  支持 indeterminate（部分选中），用于批量操作的"全选"表头。
-->
<script setup>
import { computed, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 半选（批量表头用）：仅视觉，不改变 modelValue */
  indeterminate: { type: Boolean, default: false },
  label: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const el = ref(null)
const CHECK = 'M20 6 9 17l-5-5'
const MINUS = 'M5 12h14'

const state = computed(() => {
  if (props.indeterminate) return 'mixed'
  return props.modelValue ? 'on' : 'off'
})

function syncIndeterminate() {
  if (el.value) el.value.indeterminate = props.indeterminate
}
onMounted(syncIndeterminate)
watch(() => props.indeterminate, syncIndeterminate)
</script>

<template>
  <label class="check" :class="{ dis: disabled }">
    <input
      ref="el"
      class="native"
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      :aria-checked="state === 'mixed' ? 'mixed' : modelValue"
      @change="emit('update:modelValue', $event.target.checked)"
    />
    <span class="box" :class="state" aria-hidden="true">
      <svg
        v-if="state === 'on'"
        viewBox="0 0 24 24"
        width="12"
        height="12"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path :d="CHECK" />
      </svg>
      <svg
        v-else-if="state === 'mixed'"
        viewBox="0 0 24 24"
        width="12"
        height="12"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path :d="MINUS" />
      </svg>
    </span>
    <span v-if="label" class="lab">{{ label }}</span>
  </label>
</template>

<style scoped>
.check {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
  font-size: var(--fs-sm);
  user-select: none;
}
.check.dis {
  opacity: 0.5;
  cursor: not-allowed;
}
/* 原生控件覆盖在视觉层之上：可聚焦、可读，但不可见 */
.native {
  position: absolute;
  width: 18px;
  height: 18px;
  margin: 0;
  opacity: 0;
  cursor: inherit;
}
.box {
  width: 17px;
  height: 17px;
  flex: none;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 1px;
  background: var(--sky-1);
  color: var(--sky-0);
  transition:
    background 0.22s var(--e-settle),
    border-color 0.22s var(--e-settle),
    color 0.22s var(--e-settle);
}
.check:hover:not(.dis) .box {
  border-color: var(--ink-3);
}
.box.on,
.box.mixed {
  background: var(--redshift);
  border-color: var(--redshift);
}
/* 键盘焦点画在视觉方块上（原生控件本身不可见） */
.native:focus-visible + .box {
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}
.lab {
  color: var(--ink-1);
  line-height: 1.4;
}
</style>
