<script setup>
/**
 * 应用布局 v4「墨韵 2.0」：
 * 环境氛围层（AmbientLayer）+ 顶部悬浮玻璃 Dock（DockNav）+ 居中内容区。
 * 换肤为「墨漫纸面」（rAF + clip-path，零 API 依赖）；开场编排等字体就绪后启动。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { loadBaseData } from '../composables/useBaseData'
import request from '../api/request'
import Icon from '../ui/Icon.vue'
import AmbientLayer from '../ui/AmbientLayer.vue'
import DockNav from '../ui/DockNav.vue'
import CommandPalette from '../ui/CommandPalette.vue'
import { openPalette } from '../ui/commandPalette'

const route = useRoute()
const menuOpen = ref(false)
const isNarrow = ref(false)
let mq = null

const PRIMARY_NAV = [
  { path: '/stats', title: '统计', full: '学习统计', icon: 'chart' },
  { path: '/mistakes', title: '错题库', full: '错题列表', icon: 'list' },
  { path: '/capture', title: '录入', full: '智能录入', icon: 'plus-circle' },
  { path: '/review', title: '复习', full: '今日复习', icon: 'refresh' },
  { path: '/practice', title: '练习', full: '自主练习', icon: 'pencil' },
]

const LIBRARY_NAV = [
  { path: '/vocab', title: '生词本', full: '生词本', icon: 'book' },
  { path: '/knowledge', title: '知识点', full: '知识点库', icon: 'layers' },
  { path: '/formulas', title: '公式', full: '公式背诵', icon: 'sigma' },
  { path: '/subjects', title: '科目指南', full: '科目指南', icon: 'compass' },
]

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/mistakes/')) return '/mistakes'
  return path
})

// —— 今日复习进度环 ——
const ringTotal = ref(0)
const ringDone = ref(0)

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

// —— 主题（沿用 localStorage 'km-theme'；'' = 浅色） ——
const isDark = ref(document.documentElement.dataset.theme === 'dark')

const THEME_LOOKS = {
  light:
    'radial-gradient(560px 400px at 88% -6%, rgba(193,74,49,.20), transparent 62%),' +
    'radial-gradient(680px 480px at -8% 108%, rgba(61,111,104,.18), transparent 62%),' +
    'radial-gradient(460px 340px at 52% 58%, rgba(168,132,44,.12), transparent 65%), #f5f1e8',
  dark:
    'radial-gradient(560px 400px at 88% -6%, rgba(224,88,61,.20), transparent 62%),' +
    'radial-gradient(680px 480px at -8% 108%, rgba(95,148,140,.17), transparent 62%),' +
    'radial-gradient(460px 340px at 52% 58%, rgba(210,168,63,.12), transparent 65%), #141110',
}
const veilEl = ref(null)
let themeBusy = false

function applyTheme(dark, persist = true) {
  isDark.value = dark
  document.documentElement.dataset.theme = dark ? 'dark' : ''
  if (persist) localStorage.setItem('km-theme', dark ? 'dark' : 'light')
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', dark ? '#141110' : '#f5f1e8')
}

function toggleTheme(event) {
  if (themeBusy) return
  const next = !isDark.value
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || !veilEl.value) {
    applyTheme(next)
    return
  }
  themeBusy = true
  const rect = event?.currentTarget?.getBoundingClientRect?.()
  const x = rect ? rect.left + rect.width / 2 : window.innerWidth - 60
  const y = rect ? rect.top + rect.height / 2 : 40
  const veil = veilEl.value
  veil.style.background = THEME_LOOKS[next ? 'dark' : 'light']
  veil.style.opacity = '1'
  veil.style.clipPath = `circle(0px at ${x}px ${y}px)`
  veil.style.display = 'block'
  const R = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y)) + 60
  const dur = 620
  const t0 = performance.now()
  const grow = (t) => {
    const p = Math.min(1, (t - t0) / dur)
    const eased = 1 - Math.pow(1 - p, 3)
    veil.style.clipPath = `circle(${R * eased}px at ${x}px ${y}px)`
    if (p < 1) {
      requestAnimationFrame(grow)
      return
    }
    applyTheme(next) // 墨已盖满：此刻才真正换肤
    veil.style.transition = 'opacity .18s ease'
    veil.style.opacity = '0'
    setTimeout(() => {
      veil.style.display = 'none'
      veil.style.transition = ''
      themeBusy = false
    }, 190)
  }
  requestAnimationFrame(grow)
}

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
    loadRing()
  },
)

let healthTimer = 0
let mediaHandler = null
let systemThemeHandler = null

onMounted(() => {
  loadBaseData()
  loadRing()
  loadHealth()
  healthTimer = setInterval(loadHealth, 30000)
  window.addEventListener('km:review-saved', loadRing)
  // 窄屏：Dock 收起，改为紧凑顶栏 + 抽屉
  mq = window.matchMedia('(max-width: 1100px)')
  isNarrow.value = mq.matches
  mediaHandler = () => {
    isNarrow.value = mq.matches
  }
  mq.addEventListener?.('change', mediaHandler)
  // 从未手动选过主题 → 跟随系统（用户点换肤后写入 km-theme 即固定）
  if (!localStorage.getItem('km-theme')) {
    const systemMQ = window.matchMedia('(prefers-color-scheme: dark)')
    applyTheme(systemMQ.matches, false)
    systemThemeHandler = (e) => {
      if (!localStorage.getItem('km-theme')) applyTheme(e.matches, false)
    }
    systemMQ.addEventListener?.('change', systemThemeHandler)
  }
  // 开场编排：等字体就绪（本地字体毫秒级；700ms 兜底）再放下 Dock / 显影氛围
  const arm = () => document.body.classList.add('app-ready')
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(arm)
    setTimeout(arm, 700)
  } else {
    setTimeout(arm, 200)
  }
})

onUnmounted(() => {
  clearInterval(healthTimer)
  window.removeEventListener('km:review-saved', loadRing)
  mq?.removeEventListener?.('change', mediaHandler)
  if (systemThemeHandler) {
    window.matchMedia('(prefers-color-scheme: dark)').removeEventListener?.('change', systemThemeHandler)
  }
})
</script>

<template>
  <div class="layout">
    <AmbientLayer />
    <div ref="veilEl" class="theme-veil" aria-hidden="true"></div>

    <!-- 桌面端：顶部悬浮 Dock -->
    <DockNav
      v-if="!isNarrow"
      :primary-nav="PRIMARY_NAV"
      :library-nav="LIBRARY_NAV"
      :active-path="activeMenu"
      :ring-done="ringDone"
      :ring-total="ringTotal"
      :backend-ok="backendOk"
      :is-dark="isDark"
      @toggle-theme="toggleTheme"
      @open-search="openPalette"
    />

    <!-- 窄屏：紧凑顶栏 + 抽屉 -->
    <header v-if="isNarrow" class="mobile-bar">
      <router-link to="/stats" class="mb-brand">
        <span class="mb-seal">研</span>
        <b>研错本</b>
      </router-link>
      <span class="mb-ring num" :title="`今日复习 ${ringDone}/${ringTotal}`">{{ ringDone }}<i>/{{ ringTotal }}</i></span>
      <button type="button" class="mb-btn" aria-label="搜索" @click="openPalette"><Icon name="search" :size="17" /></button>
      <button type="button" class="mb-btn" :aria-label="isDark ? '浅色模式' : '深色模式'" @click="toggleTheme">
        <Icon :name="isDark ? 'sun' : 'moon'" :size="17" />
      </button>
      <button type="button" class="mb-btn" aria-label="打开菜单" @click="menuOpen = !menuOpen"><Icon name="menu" :size="18" /></button>
    </header>

    <Transition name="drawer">
      <div v-if="menuOpen" class="drawer-mask" @click="menuOpen = false"></div>
    </Transition>
    <Transition name="drawer">
      <nav v-if="menuOpen" class="drawer">
        <div class="drawer-head">
          <span class="mb-seal">研</span>
          <b class="serif">研错本</b>
          <button type="button" class="mb-btn" @click="menuOpen = false"><Icon name="x" :size="16" /></button>
        </div>
        <p class="drawer-label">工作台</p>
        <router-link v-for="item in PRIMARY_NAV" :key="item.path" :to="item.path" class="drawer-link" :class="{ active: activeMenu === item.path }">
          <Icon :name="item.icon" :size="17" />{{ item.full }}
        </router-link>
        <p class="drawer-label">资料库</p>
        <router-link v-for="item in LIBRARY_NAV" :key="item.path" :to="item.path" class="drawer-link" :class="{ active: activeMenu === item.path }">
          <Icon :name="item.icon" :size="17" />{{ item.full }}
        </router-link>
      </nav>
    </Transition>

    <main class="deck">
      <router-view v-slot="{ Component }">
        <!-- duration 显式声明：后台标签页 transitionend 会被浏览器推迟，JS 计时兜底保证路由切换不被卡住 -->
        <Transition name="route" mode="out-in" :duration="{ enter: 320, leave: 180 }">
          <component :is="Component" :key="route.fullPath" />
        </Transition>
      </router-view>
    </main>

    <CommandPalette />
  </div>
</template>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 2;
}

/* 换肤遮罩：墨漫纸面 */
.theme-veil {
  position: fixed;
  inset: 0;
  z-index: 990;
  display: none;
  pointer-events: none;
  will-change: clip-path, opacity;
}

/* ---------- 内容区（给顶部 Dock 留出呼吸空间） ---------- */
.deck {
  flex: 1;
  width: 100%;
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 92px 32px 48px;
}

/* ---------- 窄屏顶栏 ---------- */
.mobile-bar {
  position: sticky;
  top: 10px;
  z-index: 920;
  margin: 10px 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 16px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.3);
  box-shadow: var(--shadow-2);
}
.mb-brand { display: flex; align-items: center; gap: 9px; text-decoration: none; color: var(--ink); margin-right: auto; }
.mb-brand b { font-family: var(--font-display); font-size: 16px; font-weight: 800; }
.mb-seal {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--accent-grad);
  color: #fff;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 15px;
  transform: rotate(-3deg);
  box-shadow: 0 2px 6px rgba(168, 51, 32, 0.35);
}
.mb-ring { font-size: 13px; color: var(--ink-2); font-weight: 700; }
.mb-ring i { font-style: normal; font-size: 11px; color: var(--ink-3); }
.mb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  transition: all 0.15s var(--ease);
}
.mb-btn:hover { background: var(--accent-soft); color: var(--accent-ink); }

/* ---------- 抽屉（窄屏） ---------- */
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 940;
  background: rgba(15, 12, 9, 0.45);
  backdrop-filter: blur(3px);
}
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 950;
  width: min(320px, 86vw);
  background: var(--surface);
  border-left: 1px solid var(--line);
  box-shadow: var(--shadow-3);
  padding: 16px 18px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.drawer-head { display: flex; align-items: center; gap: 10px; padding-bottom: 12px; border-bottom: 1px solid var(--line); margin-bottom: 8px; }
.drawer-head b { font-size: 17px; margin-right: auto; font-family: var(--font-display); }
.drawer-label { font-size: 10px; font-weight: 800; letter-spacing: 0.18em; color: var(--ink-3); padding: 10px 8px 4px; }
.drawer-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.15s var(--ease);
}
.drawer-link:hover { background: var(--surface-2); color: var(--ink); transform: translateX(3px); }
.drawer-link.active { background: var(--accent-soft); color: var(--accent-ink); }

.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s, transform 0.22s var(--ease); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from.drawer, .drawer-leave-to.drawer { transform: translateX(30px); }

/* ---------- 路由过渡 ---------- */
.route-enter-active { transition: opacity 0.3s var(--ease), transform 0.3s var(--ease); }
.route-leave-active { transition: opacity 0.16s ease, transform 0.16s ease; }
.route-enter-from { opacity: 0; transform: translateY(14px) scale(0.996); }
.route-leave-to { opacity: 0; transform: translateY(-8px); }

@media (max-width: 1100px) {
  .deck { padding: 24px 16px 40px; }
}
</style>
