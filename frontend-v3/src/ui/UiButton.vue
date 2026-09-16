<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'

import { magnetic } from '../design/motion'

const props = defineProps({
  variant: { type: String, default: 'ghost' },
  size: { type: String, default: 'md' },
  type: { type: String, default: 'button' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  magnet: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
})

const root = ref(null)
let stopMagnet = null

const classes = computed(() => {
  const list = ['btn', 'v-' + props.variant, 's-' + props.size]
  if (props.block) list.push('block')
  if (props.loading) list.push('busy')
  return list
})

onMounted(() => {
  if (props.magnet) stopMagnet = magnetic(root.value)
})
onBeforeUnmount(() => {
  if (typeof stopMagnet === 'function') stopMagnet()
})
</script>

<template>
  <button
    ref="root"
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : undefined"
  >
    <LoaderCircle v-if="loading" class="spin" :size="15" aria-hidden="true" />
    <span class="label"><slot></slot></span>
  </button>
</template>

<style scoped>
.btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 9px 17px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
  font-weight: 500;
  color: var(--ink-0);
  background: transparent;
  overflow: hidden;
  isolation: isolate;
  transition:
    transform 0.3s var(--e-flare),
    border-color 0.3s var(--e-settle),
    color 0.3s var(--e-settle);
  will-change: transform;
}
.btn.s-sm {
  padding: 6px 12px;
  font-size: 12px;
}
.btn.s-lg {
  padding: 13px 24px;
  font-size: var(--fs-body);
}
.btn.block {
  width: 100%;
}
.btn::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--sky-3);
  clip-path: inset(0 0 100% 0);
  transition: clip-path 0.5s var(--e-settle);
}
.btn:hover:not(:disabled)::before {
  clip-path: inset(0 0 0 0);
}
.btn:active:not(:disabled) {
  transform: translateY(1px) scale(0.988);
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn.v-solid {
  background: var(--redshift);
  border-color: var(--redshift);
  color: var(--sky-0);
}
.btn.v-solid::before {
  background: oklch(0.72 0.19 34);
}
.btn.v-quiet {
  border-color: transparent;
  color: var(--ink-1);
}
.btn.v-quiet::before {
  background: var(--sky-2);
}
.btn.v-danger {
  border-color: oklch(0.665 0.196 34 / 0.5);
  color: var(--redshift);
}
.btn.v-danger::before {
  background: var(--redshift);
}
.btn.v-danger:hover:not(:disabled) {
  color: var(--sky-0);
  border-color: var(--redshift);
}
.label {
  position: relative;
}
.spin {
  animation: btn-spin 0.9s linear infinite;
}
@keyframes btn-spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .btn {
    transition: none;
  }
  .spin {
    animation: none;
  }
}
</style>
