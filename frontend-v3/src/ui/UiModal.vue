<!--
  UiModal —— 弹层（星门）
  ---------------------------------------------------------------------------
  四条硬要求（都是可访问性的下限，不做"能开就行"的弹窗）：
   1. **焦点管理**：打开时把焦点移入弹层，关闭后**还给触发元素**（否则键盘用户会迷路）
   2. **Tab 循环**：焦点不许跑到弹层外（背景是 inert 的语义）
   3. **Esc 关闭**：除非显式禁用；点击遮罩也关闭（可关），但点击内容不关
   4. **滚动锁**：打开时锁 body 滚动并在关闭时恢复（含组件被卸载的情况）
  另外：Teleport 到 body（避免被父级 overflow/transform 裁切）、aria-modal、标题用 aria-labelledby。

  与 v2 的差异：v2 的 UiModal 没有焦点陷阱与焦点归还。这里补上，并写进单测。
-->
<script setup>
import { onBeforeUnmount, ref, useId, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: 'md' },
  closeOnEsc: { type: Boolean, default: true },
  closeOnBackdrop: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])

const WIDTH = { sm: '520px', md: '720px', lg: '960px', xl: '1180px' }
const uid = useId()
const panel = ref(null)
const titleId = `mt-${uid}`
/** 打开前的焦点元素：关闭后要还回去 */
let previousFocus = null

function close() {
  emit('update:modelValue', false)
}

/** 收集弹层内所有可聚焦元素（Tab 循环用） */
function focusables() {
  if (!panel.value) return []
  return Array.from(
    panel.value.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((el) => el.offsetParent !== null || el === document.activeElement)
}

function onKeydown(e) {
  if (e.key === 'Escape' && props.closeOnEsc) {
    e.stopPropagation()
    close()
    return
  }
  if (e.key !== 'Tab') return
  // 焦点陷阱：在弹层内循环，不许跑到背景页面
  const list = focusables()
  if (!list.length) return
  const first = list[0]
  const last = list[list.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      previousFocus = document.activeElement
      document.addEventListener('keydown', onKeydown, true)
      document.body.style.overflow = 'hidden'
      // 等一帧让内容渲染出来再聚焦
      requestAnimationFrame(() => {
        const list = focusables()
        ;(list[0] || panel.value)?.focus?.()
      })
    } else {
      document.removeEventListener('keydown', onKeydown, true)
      document.body.style.overflow = ''
      // 焦点归还：不还的话键盘用户会掉回页面顶部
      if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus()
      previousFocus = null
    }
  },
)

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown, true)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="modelValue" class="backdrop" @mousedown.self="closeOnBackdrop && close()">
        <div
          ref="panel"
          class="panel"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="title ? titleId : undefined"
          :style="{ maxWidth: WIDTH[size] || WIDTH.md }"
          tabindex="-1"
        >
          <header class="head">
            <h2 v-if="title" :id="titleId" class="ttl">{{ title }}</h2>
            <slot name="head"></slot>
            <button class="x" type="button" aria-label="关闭" @click="close">
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                aria-hidden="true"
              >
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </header>
          <div class="body">
            <slot></slot>
          </div>
          <footer v-if="$slots.foot" class="foot">
            <slot name="foot"></slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 92;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 7vh 16px 18px;
  overflow-y: auto;
  background: oklch(0.145 0.018 265 / 0.72);
  backdrop-filter: blur(3px);
}
.panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  max-height: 86vh;
  background: var(--sky-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  box-shadow: 0 30px 70px -40px #000000e6;
}
.panel:focus {
  outline: none;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px 18px 13px;
  border-bottom: 1px solid var(--line);
  flex: none;
}
.ttl {
  font-size: var(--fs-h2);
  font-weight: 500;
  letter-spacing: -0.02em;
}
.x {
  display: inline-flex;
  padding: 6px;
  border-radius: var(--radius);
  color: var(--ink-2);
  transition:
    color 0.25s var(--e-settle),
    background 0.25s var(--e-settle);
}
.x:hover {
  color: var(--ink-0);
  background: var(--sky-2);
}
.body {
  padding: 18px;
  overflow-y: auto;
}
.foot {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 13px 18px 15px;
  border-top: 1px solid var(--line);
  flex: none;
}

/* 星门开合：淡入 + 轻微上浮（只改 transform / opacity） */
.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.3s var(--e-settle);
}
.sheet-enter-active .panel,
.sheet-leave-active .panel {
  transition: transform 0.42s var(--e-flare);
}
.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}
.sheet-enter-from .panel,
.sheet-leave-to .panel {
  transform: translateY(14px) scale(0.985);
}
@media (prefers-reduced-motion: reduce) {
  .sheet-enter-active,
  .sheet-leave-active,
  .sheet-enter-active .panel,
  .sheet-leave-active .panel {
    transition: none;
  }
}
</style>
