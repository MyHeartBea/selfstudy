<script setup>
/** 全局命令面板：Ctrl+K 呼出；页面跳转 + 错题/知识点/公式多范围搜索。 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

import Icon from './Icon.vue'
import UiTag from './UiTag.vue'
import {
  paletteState,
  closePalette,
  openPalette,
  onPaletteInput,
  setScope,
  moveActive,
  NAV_COMMANDS,
  SCOPES,
} from './commandPalette'
import { questionTypeName, subjectName, truncate } from '../composables/useBaseData'

const router = useRouter()
const route = useRoute()

const results = computed(() => paletteState.results)
const inputEl = ref(null)

watch(
  () => paletteState.open,
  async (open) => {
    if (open) {
      document.body.style.overflow = 'hidden'
      await nextTick()
      inputEl.value?.focus()
    } else {
      document.body.style.overflow = ''
    }
  },
)

// 路由变化时同步关闭（点结果跳转后）
watch(
  () => route.fullPath,
  () => {
    if (paletteState.open) closePalette()
  },
)

function choose(item) {
  closePalette()
  if (item && item.target) router.push(item.target)
}

function onKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    paletteState.open ? closePalette() : openPalette()
    return
  }
  if (!paletteState.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    closePalette()
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveActive(1, results.value.length)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveActive(-1, results.value.length)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    const item = results.value[paletteState.activeIndex]
    if (item) choose(item)
  } else if (event.key === 'Tab') {
    // Tab 在三个范围间循环切换
    event.preventDefault()
    const idx = SCOPES.findIndex((s) => s.value === paletteState.scope)
    setScope(SCOPES[(idx + (event.shiftKey ? -1 : 1) + SCOPES.length) % SCOPES.length].value)
    if (paletteState.query.trim()) onPaletteInput(paletteState.query)
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="palette">
      <div v-if="paletteState.open" class="palette-backdrop" @mousedown.self="closePalette">
        <div class="palette" role="dialog" aria-label="命令面板">
          <div class="palette-input-row">
            <Icon name="search" :size="17" class="palette-search-icon" />
            <input
              ref="inputEl"
              :value="paletteState.query"
              class="palette-input"
              :placeholder="`搜索${SCOPES.find((s) => s.value === paletteState.scope)?.label || ''}，Tab 切换范围…`"
              @input="onPaletteInput($event.target.value)"
            />
            <kbd class="palette-kbd">ESC</kbd>
          </div>

          <div class="palette-scopes">
            <button
              v-for="scope in SCOPES"
              :key="scope.value"
              type="button"
              class="scope-chip"
              :class="{ active: paletteState.scope === scope.value }"
              @click="setScope(scope.value); onPaletteInput(paletteState.query)"
            >
              <Icon :name="scope.icon" :size="13" />
              {{ scope.label }}
            </button>
          </div>

          <div class="palette-list">
            <template v-if="!paletteState.query.trim()">
              <div class="palette-group">快速跳转</div>
              <button
                v-for="(item, i) in NAV_COMMANDS"
                :key="item.path"
                type="button"
                class="palette-item"
                :class="{ active: i === paletteState.activeIndex }"
                @click="choose(item)"
                @mousemove="paletteState.activeIndex = i"
              >
                <Icon :name="item.icon" :size="16" class="palette-item-icon" />
                <span class="palette-item-label">{{ item.label }}</span>
                <UiTag size="sm">{{ item.hint }}</UiTag>
              </button>
            </template>

            <template v-else>
              <div class="palette-group">
                {{ paletteState.searching ? '搜索中…' : `${results.length} 条结果` }}
              </div>
              <button
                v-for="(item, i) in results"
                :key="`${item.kind}-${item.id}`"
                type="button"
                class="palette-item"
                :class="{ active: i === paletteState.activeIndex }"
                @click="choose(item)"
                @mousemove="paletteState.activeIndex = i"
              >
                <Icon :name="item.kind === 'mistake' ? 'list' : item.kind === 'knowledge' ? 'book' : 'sigma'" :size="16" class="palette-item-icon" />
                <span class="palette-item-label">
                  {{ truncate(item.title, 52) }}
                  <small v-if="item.sub" class="palette-item-sub">{{ truncate(item.sub, 36) }}</small>
                </span>
                <UiTag v-if="item.kind === 'mistake'" size="sm">{{ questionTypeName(item.type) }}</UiTag>
                <UiTag v-if="item.kind === 'mistake'" size="sm" soft>{{ subjectName(item.subject) }}</UiTag>
              </button>
              <div v-if="!paletteState.searching && !results.length" class="palette-empty">
                没有匹配结果，换个关键词试试
              </div>
            </template>
          </div>

          <div class="palette-foot">
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>Tab</kbd> 换范围</span>
            <span class="palette-brand">研错本 · 命令面板</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  justify-content: center;
  padding: 10vh 16px 16px;
  background: color-mix(in srgb, var(--bg) 40%, rgba(20, 16, 12, 0.4));
  backdrop-filter: blur(4px);
}

.palette {
  width: 100%;
  max-width: 600px;
  max-height: 68vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: var(--shadow-3);
  overflow: hidden;
}

.palette-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 18px 12px;
}
.palette-search-icon { color: var(--accent); }
.palette-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 15px;
  color: var(--ink);
  outline: none;
}
.palette-input::placeholder { color: var(--ink-3); }
.palette-kbd {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 6px;
  border-radius: 6px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-3);
}

.palette-scopes {
  display: flex;
  gap: 6px;
  padding: 0 18px 12px;
  border-bottom: 1px solid var(--line);
}
.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
}
.scope-chip:hover { border-color: var(--accent); color: var(--accent-ink); }
.scope-chip.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.palette-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.palette-group {
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-3);
  padding: 8px 10px 5px;
}
.palette-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ink);
  font-size: 13.5px;
  text-align: left;
  cursor: pointer;
}
.palette-item.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.palette-item-icon { color: var(--ink-3); }
.palette-item.active .palette-item-icon { color: var(--accent); }
.palette-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.palette-item-sub {
  display: block;
  font-size: 11px;
  color: var(--ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
}
.palette-empty {
  padding: 14px;
  text-align: center;
  color: var(--ink-3);
  font-size: 13px;
}

.palette-foot {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 9px 16px;
  border-top: 1px solid var(--line);
  font-size: 11px;
  color: var(--ink-3);
  background: var(--surface-2);
}
.palette-foot kbd {
  padding: 1px 5px;
  margin-right: 3px;
  border-radius: 5px;
  border: 1px solid var(--line);
  background: var(--surface);
  font-size: 10px;
}
.palette-brand { margin-left: auto; letter-spacing: 0.06em; }

.palette-enter-active, .palette-leave-active { transition: opacity 0.18s ease; }
.palette-enter-active .palette, .palette-leave-active .palette { transition: transform 0.22s cubic-bezier(0.22, 1.2, 0.36, 1); }
.palette-enter-from, .palette-leave-to { opacity: 0; }
.palette-enter-from .palette, .palette-leave-to .palette { transform: translateY(-12px) scale(0.98); }
</style>
