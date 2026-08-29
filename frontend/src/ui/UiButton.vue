<script setup>
/** 按钮：variant = primary | ghost | outline | danger | success | subtle；size = md | sm | lg
 *  内置水波纹涟漪 + 按压缩放微交互。 */
import { ref } from 'vue'

defineProps({
  variant: { type: String, default: 'outline' },
  size: { type: String, default: 'md' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
})

const el = ref(null)
const ripples = ref([])
let rippleSeq = 0

function spawnRipple(event) {
  const host = el.value
  if (!host) return
  const rect = host.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height) * 2.1
  const x = event.clientX ? event.clientX - rect.left : rect.width / 2
  const y = event.clientY ? event.clientY - rect.top : rect.height / 2
  const id = ++rippleSeq
  ripples.value.push({ id, x: x - size / 2, y: y - size / 2, size })
  setTimeout(() => {
    ripples.value = ripples.value.filter((r) => r.id !== id)
  }, 650)
}
</script>

<template>
  <button
    ref="el"
    class="btn"
    :class="[`btn-${variant}`, `btn-${size}`, { 'btn-block': block }]"
    :disabled="disabled || loading"
    @pointerdown="spawnRipple"
  >
    <span
      v-for="r in ripples"
      :key="r.id"
      class="btn-ripple"
      :style="{ left: r.x + 'px', top: r.y + 'px', width: r.size + 'px', height: r.size + 'px' }"
    ></span>
    <span v-if="loading" class="btn-spinner" aria-hidden="true"></span>
    <span class="btn-content"><slot></slot></span>
  </button>
</template>

<style scoped>
.btn {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid transparent;
  border-radius: 10px;
  font-weight: 600;
  font-size: 13.5px;
  line-height: 1;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s,
    transform 0.09s cubic-bezier(0.22, 0.8, 0.36, 1);
  user-select: none;
}
.btn:active:not(:disabled) {
  transform: translateY(1px) scale(0.985);
}
.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 水波纹 */
.btn-ripple {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  background: radial-gradient(circle, color-mix(in srgb, currentColor 32%, transparent) 0%, transparent 62%);
  transform: scale(0);
  animation: ripple-run 0.62s cubic-bezier(0.22, 0.8, 0.36, 1) forwards;
}
@keyframes ripple-run {
  to {
    transform: scale(1);
    opacity: 0;
  }
}

.btn-content {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.btn-md { height: 36px; padding: 0 14px; }
.btn-sm { height: 30px; padding: 0 10px; font-size: 12.5px; border-radius: 8px; }
.btn-lg { height: 44px; padding: 0 20px; font-size: 14.5px; border-radius: 12px; }
.btn-block { width: 100%; }

.btn-primary {
  background: var(--accent);
  color: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.14),
    0 6px 16px -8px color-mix(in srgb, var(--accent) 70%, transparent);
}
.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.14), 0 10px 24px -8px color-mix(in srgb, var(--accent) 80%, transparent);
}

.btn-outline {
  background: var(--surface);
  border-color: var(--line-strong);
  color: var(--ink);
}
.btn-outline:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-ink);
  background: var(--accent-soft);
}

.btn-ghost {
  background: transparent;
  color: var(--ink-2);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--ink);
}

.btn-subtle {
  background: var(--surface-2);
  color: var(--ink);
  border-color: var(--line);
}
.btn-subtle:hover:not(:disabled) { border-color: var(--line-strong); }

.btn-danger {
  background: transparent;
  border-color: color-mix(in srgb, var(--red) 40%, transparent);
  color: var(--red);
}
.btn-danger:hover:not(:disabled) {
  background: var(--red-soft);
  border-color: var(--red);
}

.btn-success {
  background: var(--green);
  color: #fff;
}
.btn-success:hover:not(:disabled) { filter: brightness(1.06); }

.btn-spinner {
  position: relative;
  width: 13px;
  height: 13px;
  flex: none;
  border-radius: 50%;
  border: 2px solid color-mix(in srgb, currentColor 30%, transparent);
  border-top-color: currentColor;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
