<script setup>
/**
 * 顶部悬浮玻璃 Dock（墨韵 2.0）：
 * 品牌印章 + 主导航 + 资料库 + 复习环 + 搜索 + 换肤，胶囊悬浮居中。
 * active 高亮 pill 沿横向弹性滑动；悬停浮出玻璃标签。
 */
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import Icon from '../ui/Icon.vue'

const props = defineProps({
  primaryNav: { type: Array, required: true },
  libraryNav: { type: Array, required: true },
  activePath: { type: String, required: true },
  ringDone: { type: Number, default: 0 },
  ringTotal: { type: Number, default: 0 },
  backendOk: { type: Boolean, default: null },
  isDark: { type: Boolean, default: false },
})
const emit = defineEmits(['toggle-theme', 'open-search'])

const route = useRoute()
const router = useRouter()
const dockEl = ref(null)
const indEl = ref(null)
const RING_R = 15.5
const RING_C = 2 * Math.PI * RING_R

const ringPercent = () =>
  props.ringTotal ? Math.min(100, Math.round((props.ringDone / props.ringTotal) * 100)) : 0

function moveInd() {
  const el = dockEl.value?.querySelector('.dock-item.active')
  if (el && indEl.value) indEl.value.style.transform = `translateX(${el.offsetLeft}px)`
}

function go(path) {
  if (route.path !== path) router.push(path)
}

watch(
  () => props.activePath,
  () => nextTick(moveInd),
)
onMounted(() => {
  nextTick(moveInd)
  setTimeout(moveInd, 350) // 字体就绪后宽度微调的兜底
})
</script>

<template>
  <nav ref="dockEl" class="dock" aria-label="主导航">
    <router-link to="/stats" class="dock-logo" data-label="研错本 · 学习统计">
      <span class="seal">研</span>
    </router-link>
    <span class="dock-sep"></span>
    <button
      v-for="item in primaryNav"
      :key="item.path"
      type="button"
      class="dock-item"
      :class="{ active: activePath === item.path }"
      :data-label="item.full"
      @click="go(item.path)"
    >
      <Icon :name="item.icon" :size="18" />
    </button>
    <span class="dock-sep"></span>
    <button
      v-for="item in libraryNav"
      :key="item.path"
      type="button"
      class="dock-item"
      :class="{ active: activePath === item.path }"
      :data-label="item.full"
      @click="go(item.path)"
    >
      <Icon :name="item.icon" :size="18" />
    </button>
    <span class="dock-sep"></span>
    <button
      type="button"
      class="dock-item ring-item"
      data-label="今日复习进度"
      @click="go('/review')"
    >
      <svg viewBox="0 0 40 40" class="ring-svg" aria-hidden="true">
        <circle class="ring-track" cx="20" cy="20" :r="RING_R" />
        <circle
          class="ring-value"
          cx="20"
          cy="20"
          :r="RING_R"
          :stroke-dasharray="RING_C"
          :stroke-dashoffset="RING_C * (1 - ringPercent() / 100)"
        />
      </svg>
      <b class="num">{{ ringDone }}</b><i>/{{ ringTotal }}</i>
    </button>
    <button type="button" class="dock-item" data-label="全局搜索 Ctrl K" @click="emit('open-search')">
      <Icon name="search" :size="18" />
    </button>
    <button
      type="button"
      class="dock-item"
      :data-label="isDark ? '换浅色 · 墨漫纸面' : '换深色 · 墨漫纸面'"
      @click="emit('toggle-theme', $event)"
    >
      <Icon :name="isDark ? 'sun' : 'moon'" :size="18" />
    </button>
    <span class="status-dot" :class="{ bad: backendOk === false }" data-label="本地数据状态"></span>
    <div ref="indEl" class="dock-ind" aria-hidden="true"></div>
  </nav>
</template>

<style scoped>
.dock {
  position: fixed;
  top: 14px;
  left: 50%;
  transform: translateX(-50%) translateY(-18px);
  z-index: 920;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 3px;
  padding: 8px 12px;
  border-radius: 18px;
  background: var(--glass);
  backdrop-filter: blur(22px) saturate(1.3);
  box-shadow: var(--shadow-2);
  opacity: 0;
  transition: opacity 0.55s var(--ease), transform 0.65s var(--spring), background-color 0.4s var(--ease);
}
:global(body.app-ready .dock) {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
.dock::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 18px;
  padding: 1px;
  background: linear-gradient(
    160deg,
    color-mix(in srgb, #fff 40%, transparent),
    transparent 40%,
    color-mix(in srgb, var(--accent) 18%, transparent)
  );
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.dock-logo {
  width: 42px;
  height: 42px;
  margin-right: 4px;
  display: grid;
  place-items: center;
  text-decoration: none;
}
.seal {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--accent-grad);
  color: #fff;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 19px;
  box-shadow: 0 2px 8px rgba(168, 51, 32, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.25);
  transform: rotate(-3deg);
  animation: seal-breathe 5s ease-in-out infinite;
}
@keyframes seal-breathe {
  0%, 100% { transform: rotate(-3deg) scale(1); }
  50% { transform: rotate(-1.5deg) scale(1.06); }
}

.dock-sep { width: 1px; height: 26px; background: var(--line); margin: 0 5px; flex: none; }

.dock-item {
  position: relative;
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 13px;
  background: transparent;
  color: var(--ink-3);
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
  transition: color 0.2s var(--ease), background 0.2s var(--ease), transform 0.25s var(--spring);
}
.dock-item:hover { color: var(--ink); transform: scale(1.12) translateY(-1px); }
.dock-item:active { transform: scale(0.94); }
.dock-item.active { color: var(--accent); }

.ring-item { width: auto; padding: 0 12px; gap: 5px; display: inline-flex; align-items: center; }
.ring-svg { width: 26px; height: 26px; transform: rotate(-90deg); }
.ring-track { fill: none; stroke: var(--line-strong); stroke-width: 4.5; }
.ring-value {
  fill: none;
  stroke: var(--accent);
  stroke-width: 4.5;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.9s var(--ease);
}
.ring-item b { font-family: var(--font-display); font-size: 14px; color: var(--ink); }
.ring-item i { font-style: normal; font-size: 11px; color: var(--ink-3); }

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin: 0 4px 0 6px;
  background: var(--green);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--green) 16%, transparent);
  animation: dot-pulse 2.4s ease-in-out infinite;
}
.status-dot.bad { background: var(--red); box-shadow: 0 0 0 3px color-mix(in srgb, var(--red) 16%, transparent); }
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 0 2px color-mix(in srgb, var(--green) 12%, transparent); }
  50% { box-shadow: 0 0 0 4px color-mix(in srgb, var(--green) 22%, transparent); }
}

.dock-ind {
  position: absolute;
  left: 0;
  top: 8px;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--accent-soft);
  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--accent) 30%, transparent);
  transition: transform 0.38s var(--spring);
  z-index: -1;
}

/* 悬浮玻璃标签 */
.dock-item::after,
.dock-logo::after,
.status-dot::after {
  content: attr(data-label);
  position: absolute;
  left: 50%;
  top: calc(100% + 12px);
  translate: -50% 0;
  white-space: nowrap;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
  background: var(--glass);
  backdrop-filter: blur(14px);
  padding: 5px 12px;
  border-radius: 9px;
  box-shadow: var(--shadow-2);
  opacity: 0;
  transform: translateY(-5px) scale(0.94);
  transition: all 0.22s var(--spring);
  pointer-events: none;
  z-index: 30;
}
.dock-item:hover::after,
.dock-logo:hover::after,
.status-dot:hover::after { opacity: 1; transform: translateY(0) scale(1); }

@media (max-width: 1240px) {
  .ring-item i { display: none; }
  .dock { gap: 1px; padding: 8px 9px; }
}
@media (max-width: 1100px) {
  .dock { display: none; }
}
</style>
