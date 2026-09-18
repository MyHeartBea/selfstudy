<script>
// 标题 id 计数器必须放普通 script：`<script setup>` 里的声明每个实例都会重跑一遍。
let seq = 0
const nextTitleId = () => `ui-modal-title-${++seq}`
</script>

<script setup>
/** 模态框：teleport 到 body，Esc 关闭、焦点圈在面板内、滚动锁定、宽档 size = sm | md | lg | xl */
import { nextTick, onUnmounted, ref, watch } from 'vue'
import { lockBodyScroll, unlockBodyScroll } from './scrollLock'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  size: { type: String, default: 'md' },
  closeOnEsc: { type: Boolean, default: true },
  // 弹窗层级：普通弹窗默认 1000；确认弹窗（ConfirmHost）传入更高值以盖在其他弹窗之上。
  zIndex: { type: Number, default: 1000 },
})

const emit = defineEmits(['update:modelValue'])

const WIDTH = { sm: '560px', md: '760px', lg: '1000px', xl: '1220px' }

const titleId = nextTitleId()

const panelEl = ref(null)

function close() {
  emit('update:modelValue', false)
}

// 弹窗可以叠（确认框盖在编辑弹窗上），锁要计数：见 ui/scrollLock.js。
let locked = false
function setScrollLock(on) {
  if (locked === on) return
  locked = on
  if (on) lockBodyScroll()
  else unlockBodyScroll()
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

let returnFocus = null

// Teleport 出去的内层弹窗与外层是 body 下的兄弟，不在其 panel 里，
// 所以用 target 是否落在本面板内来判断"Tab 该不该由我处理"。
function onKeydown(event) {
  if (event.key === 'Escape') {
    if (props.closeOnEsc && props.modelValue) {
      event.stopPropagation()
      close()
    }
    return
  }
  if (event.key !== 'Tab' || !panelEl.value) return
  const panel = panelEl.value
  if (!panel.contains(event.target)) return
  const items = Array.from(panel.querySelectorAll(FOCUSABLE)).filter(
    (el) => el.getClientRects().length,
  )
  if (!items.length) {
    event.preventDefault()
    panel.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === panel)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      returnFocus = document.activeElement
      document.addEventListener('keydown', onKeydown, true)
      setScrollLock(true)
      // 焦点落到面板本身（tabindex=-1）：读屏会念出 dialog 与标题，
      // Tab 也从面板顶部开始，而不是留在被遮住的上一个页面里。
      // 内容自己抢了焦点（ConfirmHost 的确认输入框）就不抢回来。
      await nextTick()
      const panel = panelEl.value
      if (panel && !panel.contains(document.activeElement)) panel.focus({ preventScroll: true })
    } else {
      document.removeEventListener('keydown', onKeydown, true)
      setScrollLock(false)
      if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true })
      returnFocus = null
    }
  },
  // 必须 immediate：不少调用方是"以 modelValue=true 直接挂载"（KnowledgeEditModal 就是这样），
  // 只监听 false->true 的话这类弹窗既没有焦点圈也没有 Esc。见 AGENTS.md 弹窗状态一条。
  { immediate: true },
)

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown, true)
  setScrollLock(false)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-backdrop"
        data-lenis-prevent
        :style="{ zIndex: props.zIndex }"
        @mousedown.self="close()"
      >
        <div
          ref="panelEl"
          class="modal-panel"
          tabindex="-1"
          :style="{ maxWidth: WIDTH[size] || WIDTH.md }"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <header class="modal-head">
            <h3 :id="titleId" class="modal-title">{{ title }}</h3>
            <button class="modal-close" aria-label="关闭" @click="close">
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              >
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </header>
          <div class="modal-body">
            <slot></slot>
          </div>
          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer"></slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 6vh 16px 16px;
  background: color-mix(in srgb, var(--bg) 45%, rgba(20, 16, 12, 0.45));
  backdrop-filter: blur(3px);
  overflow-y: auto;
}

.modal-panel {
  width: 100%;
  background:
    linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(
        160deg,
        color-mix(in srgb, var(--accent) 22%, transparent),
        transparent 42%,
        color-mix(in srgb, var(--gold) 16%, transparent)
      )
      border-box;
  border: 1px solid transparent;
  border-radius: var(--r-xl);
  box-shadow: var(--shadow-3);
  backdrop-filter: blur(18px) saturate(1.2);
  display: flex;
  flex-direction: column;
  max-height: 88vh;
}

.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 22px 14px;
  border-bottom: 1px solid var(--line);
  flex: none;
}

.modal-title {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
}

.modal-close {
  display: inline-flex;
  padding: 6px;
  border: none;
  border-radius: 9px;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  transition: all var(--dur-1) var(--ease);
}
.modal-close:hover {
  background: var(--surface-2);
  color: var(--ink);
  transform: rotate(90deg);
}

.modal-body {
  padding: 18px 22px;
  overflow-y: auto;
}

.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 22px 16px;
  border-top: 1px solid var(--line);
  flex: none;
}

/* 弹层统一时序：进场有回弹、离场干脆。
   之前 enter 和 leave 共用一条 transition，关窗也带 300ms 弹簧，拖沓。 */
.modal-enter-active {
  transition: opacity var(--dur-2) var(--ease-enter);
}
.modal-leave-active {
  transition: opacity var(--dur-1) var(--ease-exit);
}
.modal-enter-active .modal-panel {
  transition: transform var(--dur-3) var(--ease-spring);
}
.modal-leave-active .modal-panel {
  transition: transform var(--dur-1) var(--ease-exit);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: translateY(18px) scale(0.96);
}
</style>
