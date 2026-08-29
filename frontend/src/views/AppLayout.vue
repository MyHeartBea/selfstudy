<script setup>
/**
 * 应用布局 v3「墨·纸·印」：
 * 顶部杂志式报头导航（粗墨双线页眉）+ 纸面内容区。
 * 与旧版左侧栏骨架完全不同。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { loadBaseData } from '../composables/useBaseData'
import request from '../api/request'
import Icon from '../ui/Icon.vue'
import CommandPalette from '../ui/CommandPalette.vue'
import { openPalette } from '../ui/commandPalette'

const route = useRoute()
const menuOpen = ref(false)

const PRIMARY_NAV = [
  { path: '/stats', title: '统计', full: '学习统计', icon: 'chart' },
  { path: '/mistakes', title: '错题库', full: '错题列表', icon: 'list' },
  { path: '/capture', title: '录入', full: '智能录入', icon: 'plus-circle' },
  { path: '/review', title: '复习', full: '今日复习', icon: 'refresh' },
  { path: '/practice', title: '练习', full: '自主练习', icon: 'pencil' },
]

const LIBRARY_NAV = [
  { path: '/vocab', title: '生词本', icon: 'book' },
  { path: '/knowledge', title: '知识点', icon: 'layers' },
  { path: '/formulas', title: '公式', icon: 'sigma' },
  { path: '/subjects', title: '科目指南', icon: 'compass' },
]

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/mistakes/')) return '/mistakes'
  return path
})

const pageTitle = computed(() => {
  const map = {
    '/stats': '学习统计',
    '/mistakes': '错题列表',
    '/capture': '智能录入',
    '/review': '今日复习',
    '/practice': '自主练习',
    '/vocab': '生词本',
    '/knowledge': '知识点库',
    '/formulas': '公式背诵',
    '/subjects': '科目指南',
  }
  return map[activeMenu.value] || (route.name === 'mistake-edit' ? '编辑错题' : '学习工作台')
})

const today = ref('')

function refreshDate() {
  today.value = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
}

// —— 今日复习进度 ——
const ringTotal = ref(0)
const ringDone = ref(0)
const ringPercent = computed(() =>
  ringTotal.value ? Math.min(100, Math.round((ringDone.value / ringTotal.value) * 100)) : 0,
)
const RING_R = 15.5
const RING_C = 2 * Math.PI * RING_R

async function loadRing() {
  try {
    const res = await request.get('/reviews/stats', { silent: true })
    const data = res.data.data || {}
    ringTotal.value = Number(data.due_today) || 0
    ringDone.value = Number(data.reviewed_today) || 0
  } catch (err) {}
}

const backendOk = ref(null)

async function loadHealth() {
  try {
    const res = await request.get('/health', { silent: true })
    backendOk.value = res.data.data?.status === 'ok'
  } catch (err) {
    backendOk.value = false
  }
}

const isDark = ref(document.documentElement.dataset.theme === 'dark')

function toggleTheme(event) {
  const apply = () => {
    isDark.value = !isDark.value
    document.documentElement.dataset.theme = isDark.value ? 'dark' : ''
    localStorage.setItem('km-theme', isDark.value ? 'dark' : 'light')
    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) meta.setAttribute('content', isDark.value ? '#16130f' : '#c2402a')
  }
  if (document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const x = event?.clientX ?? window.innerWidth - 60
    const y = event?.clientY ?? 40
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))
    const transition = document.startViewTransition(apply)
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 480, easing: 'cubic-bezier(0.22, 0.8, 0.36, 1)', pseudoElement: '::view-transition-new(root)' },
      )
    })
  } else {
    apply()
  }
}

watch(
  () => route.fullPath,
  () => {
    refreshDate()
    menuOpen.value = false
    loadRing()
  },
)

onMounted(() => {
  loadBaseData()
  refreshDate()
  loadRing()
  loadHealth()
  setInterval(loadHealth, 30000)
  window.addEventListener('km:review-saved', loadRing)
})
</script>

<template>
  <div class="layout">
    <!-- 顶部报头：粗墨双线 + 水平导航 -->
    <header class="masthead">
      <div class="mast-inner">
        <router-link to="/stats" class="brand">
          <span class="brand-seal serif">研</span>
          <span class="brand-copy">
            <b class="brand-title serif">研错本</b>
            <i class="brand-sub">KAOYAN MISTAKE BOOK</i>
          </span>
        </router-link>

        <nav class="mast-nav">
          <router-link
            v-for="item in PRIMARY_NAV"
            :key="item.path"
            :to="item.path"
            class="mast-link"
            :class="{ active: activeMenu === item.path }"
          >
            <span class="mast-link-cn">{{ item.title }}</span>
            <span class="mast-link-en">{{ item.full }}</span>
          </router-link>
        </nav>

        <div class="mast-actions">
          <span class="ring-chip" :title="`今日复习 ${ringDone}/${ringTotal}`">
            <svg viewBox="0 0 40 40" class="ring-svg" aria-hidden="true">
              <circle class="ring-track" cx="20" cy="20" :r="RING_R" />
              <circle
                class="ring-value"
                cx="20"
                cy="20"
                :r="RING_R"
                :stroke-dasharray="RING_C"
                :stroke-dashoffset="RING_C * (1 - ringPercent / 100)"
              />
            </svg>
            <b>{{ ringDone }}</b><i>/{{ ringTotal }}</i>
          </span>

          <button type="button" class="mast-search" @click="openPalette">
            <Icon name="search" :size="14" />
            <span>搜索</span>
            <kbd>Ctrl K</kbd>
          </button>

          <button type="button" class="icon-btn" :title="isDark ? '浅色模式' : '深色模式'" @click="toggleTheme">
            <Icon :name="isDark ? 'sun' : 'moon'" :size="16" />
          </button>

          <button type="button" class="icon-btn burger" aria-label="打开菜单" @click="menuOpen = !menuOpen">
            <Icon name="menu" :size="17" />
          </button>

          <span class="mast-date">{{ today }}</span>
        </div>
      </div>
      <!-- 报头粗墨线 + 细线（报纸页眉） -->
      <div class="mast-rule" aria-hidden="true"></div>
    </header>

    <!-- 移动端全屏抽屉 -->
    <Transition name="drawer">
      <div v-if="menuOpen" class="drawer-mask" @click="menuOpen = false"></div>
    </Transition>
    <Transition name="drawer">
      <nav v-if="menuOpen" class="drawer">
        <div class="drawer-head">
          <span class="brand-seal serif">研</span>
          <b class="serif">研错本</b>
          <button type="button" class="icon-btn" @click="menuOpen = false"><Icon name="x" :size="16" /></button>
        </div>
        <p class="drawer-label">工作台</p>
        <router-link v-for="item in PRIMARY_NAV" :key="item.path" :to="item.path" class="drawer-link" :class="{ active: activeMenu === item.path }">
          <Icon :name="item.icon" :size="17" />{{ item.full }}
        </router-link>
        <p class="drawer-label">资料库</p>
        <router-link v-for="item in LIBRARY_NAV" :key="item.path" :to="item.path" class="drawer-link" :class="{ active: activeMenu === item.path }">
          <Icon :name="item.icon" :size="17" />{{ item.title }}
        </router-link>
      </nav>
    </Transition>

    <!-- 桌面端资料库次级条 -->
    <div class="subnav">
      <div class="subnav-inner">
        <span class="subnav-label">资料库</span>
        <router-link
          v-for="item in LIBRARY_NAV"
          :key="item.path"
          :to="item.path"
          class="subnav-link"
          :class="{ active: activeMenu === item.path }"
        >
          <Icon :name="item.icon" :size="13" />
          {{ item.title }}
        </router-link>
        <span class="subnav-right">
          <span class="status-dot" :class="{ bad: backendOk === false }" :title="backendOk === false ? '后端未连接' : '后端运行中'"></span>
          {{ backendOk === false ? '后端离线' : '本地数据' }}
        </span>
      </div>
    </div>

    <main class="deck">
      <router-view v-slot="{ Component }">
        <Transition name="route" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </Transition>
      </router-view>
    </main>

    <footer class="colophon">
      <span class="serif">研错本</span>
      <span>km-v2 · 墨纸印 · 本地运行</span>
    </footer>

    <CommandPalette />
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ---------- 报头 ---------- */
.masthead {
  position: sticky;
  top: 0;
  z-index: 900;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(14px);
}

.mast-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 12px 28px 10px;
  display: flex;
  align-items: center;
  gap: 26px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  flex: none;
}
.brand-seal {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--accent);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  transform: rotate(-4deg);
  box-shadow: 2.5px 2.5px 0 color-mix(in srgb, var(--ink) 82%, transparent);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.brand:hover .brand-seal { transform: rotate(3deg) scale(1.05); }
.brand-copy { display: flex; flex-direction: column; line-height: 1.15; }
.brand-title { font-size: 19px; font-weight: 800; letter-spacing: 0.06em; color: var(--ink); }
.brand-sub {
  font-style: normal;
  font-size: 8.5px;
  letter-spacing: 0.24em;
  color: var(--ink-3);
}

.mast-nav {
  display: flex;
  align-items: stretch;
  gap: 4px;
  margin-left: 6px;
}
.mast-link {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
  padding: 5px 13px 7px;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.15s;
}
.mast-link:hover { background: var(--surface-2); }
.mast-link-cn {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--ink-2);
  letter-spacing: 0.05em;
}
.mast-link-en {
  font-size: 8px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3);
  opacity: 0.75;
}
.mast-link.active .mast-link-cn {
  color: var(--accent-ink);
}
.mast-link.active {
  background: var(--accent-soft);
}
.mast-link.active .mast-link-en { color: var(--accent-ink); opacity: 0.9; }

.mast-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.ring-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 4px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--surface);
}
.ring-svg { width: 26px; height: 26px; transform: rotate(-90deg); }
.ring-track { fill: none; stroke: var(--line); stroke-width: 4.5; }
.ring-value {
  fill: none;
  stroke: var(--accent);
  stroke-width: 4.5;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.9s cubic-bezier(0.22, 0.8, 0.36, 1);
}
.ring-chip b { font-family: var(--font-display); font-size: 14px; color: var(--ink); }
.ring-chip i { font-style: normal; font-size: 11px; color: var(--ink-3); }

.mast-search {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 8px 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-3);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.15s;
}
.mast-search:hover { border-color: var(--accent); color: var(--accent-ink); }
.mast-search kbd {
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 4px;
  border: 1px solid var(--line);
  background: var(--surface-2);
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.15s;
}
.icon-btn:hover { border-color: var(--accent); color: var(--accent-ink); }
.burger { display: none; }

.mast-date {
  font-size: 11.5px;
  color: var(--ink-3);
  letter-spacing: 0.04em;
  writing-mode: horizontal-tb;
  max-width: 150px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 报头规则线：粗墨线 + 细红线 */
.mast-rule {
  height: 3px;
  background: linear-gradient(to bottom, var(--ink) 0 2px, transparent 2px 3px),
    linear-gradient(to right, var(--accent), color-mix(in srgb, var(--accent) 25%, transparent));
  background-size: 100% 3px, 220px 3px;
  background-repeat: no-repeat;
}

/* ---------- 资料库次级条 ---------- */
.subnav {
  border-bottom: 1px solid var(--line);
  background: color-mix(in srgb, var(--bg) 72%, transparent);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 65px;
  z-index: 880;
}
.subnav-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 7px 28px;
  display: flex;
  align-items: center;
  gap: 18px;
}
.subnav-label {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: var(--ink-3);
}
.subnav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-2);
  padding: 3px 10px;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.14s;
}
.subnav-link:hover { color: var(--accent-ink); background: var(--accent-soft); }
.subnav-link.active {
  color: var(--accent-ink);
  text-decoration: underline;
  text-decoration-color: var(--accent);
  text-decoration-thickness: 2px;
  text-underline-offset: 5px;
}
.subnav-right {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: var(--ink-3);
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--green) 16%, transparent);
  animation: dot-pulse 2.4s ease-in-out infinite;
}
.status-dot.bad { background: var(--red); box-shadow: 0 0 0 3px color-mix(in srgb, var(--red) 16%, transparent); }
@keyframes dot-pulse {
  0%, 100% { box-shadow: 0 0 0 2px color-mix(in srgb, var(--green) 12%, transparent); }
  50% { box-shadow: 0 0 0 4px color-mix(in srgb, var(--green) 22%, transparent); }
}

/* ---------- 内容区 ---------- */
.deck {
  flex: 1;
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  padding: 6px 28px 40px;
}

.colophon {
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
  padding: 18px 28px 26px;
  border-top: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--ink-3);
  letter-spacing: 0.08em;
}
.colophon .serif { font-size: 13px; font-weight: 700; }

/* ---------- 路由过渡 ---------- */
.route-enter-active {
  transition: opacity 0.3s cubic-bezier(0.22, 0.8, 0.36, 1), transform 0.3s cubic-bezier(0.22, 0.8, 0.36, 1);
}
.route-leave-active { transition: opacity 0.16s ease, transform 0.16s ease; }
.route-enter-from { opacity: 0; transform: translateY(16px) scale(0.995); }
.route-leave-to { opacity: 0; transform: translateY(-8px); }

/* ---------- 移动端抽屉 ---------- */
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 940;
  background: rgba(15, 12, 9, 0.45);
}
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 950;
  width: min(320px, 86vw);
  background: var(--surface);
  border-left: 2px solid var(--ink);
  padding: 16px 18px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.drawer-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--ink);
  margin-bottom: 8px;
}
.drawer-head b { font-size: 17px; margin-right: auto; }
.drawer-label {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: var(--ink-3);
  padding: 10px 8px 4px;
}
.drawer-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
}
.drawer-link:hover { background: var(--surface-2); color: var(--ink); }
.drawer-link.active { background: var(--accent-soft); color: var(--accent-ink); }

.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s, transform 0.22s cubic-bezier(0.22, 0.8, 0.36, 1); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from.drawer, .drawer-leave-to.drawer { transform: translateX(30px); }

@media (max-width: 1080px) {
  .mast-nav { display: none; }
  .subnav { display: none; }
  .burger { display: inline-flex; }
  .mast-date { display: none; }
  .mast-inner { padding: 10px 16px 8px; gap: 14px; }
  .deck { padding: 6px 16px 32px; }
  .colophon { padding: 14px 16px 22px; }
}
@media (min-width: 1081px) {
  .drawer, .drawer-mask { display: none; }
}
</style>

<style>
/* View Transition 换肤圆形扩散 */
::view-transition-old(root),
::view-transition-new(root) {
  animation: none;
  mix-blend-mode: normal;
}
::view-transition-old(root) { z-index: 1; }
::view-transition-new(root) { z-index: 2; }
</style>
