<script setup>
/**
 * 应用布局 v4「墨韵 2.0」：
 * 环境氛围层（AmbientLayer）+ 顶部悬浮玻璃 Dock（DockNav）+ 居中内容区。
 * 换肤为「墨漫纸面」（rAF + clip-path，零 API 依赖）；开场编排等字体就绪后启动。
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { pageDir } from '../composables/pageFlip'

import { loadBaseData } from '../composables/useBaseData'
import request from '../api/request'
import Icon from '../ui/Icon.vue'
import AmbientLayer from '../ui/AmbientLayer.vue'
import ShaderBackdrop from '../ui/ShaderBackdrop.vue'
import DockNav from '../ui/DockNav.vue'
import ExamCountdown from '../ui/ExamCountdown.vue'
import CommandPalette from '../ui/CommandPalette.vue'
import UiModal from '../ui/UiModal.vue'
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
  { path: '/papers', title: '真题库', full: '真题库', icon: 'notebook' },
  { path: '/essays', title: '作文', full: '作文档案', icon: 'pencil' },
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
const shortcutsOpen = ref(false)

// —— 全局考研倒计时（外壳取一次，10 分钟刷一次；跨天由刷新兜住） ——
const examDays = ref(null)
const examDate = ref('')
const examPassed = ref(false)

async function loadExam() {
  try {
    const res = await request.get('/exam-countdown', { silent: true })
    const data = res.data.data || {}
    examDays.value = data.days === null || data.days === undefined ? null : Number(data.days)
    examDate.value = data.date || ''
    examPassed.value = !!data.passed
  } catch (err) {
    examDays.value = null
  }
}

const SHORTCUT_ROWS = [
  ['全局搜索 · 命令面板', 'Ctrl + K'],
  ['快捷键速查', '?'],
  ['复习：选项作答', '1-7 / A-G'],
  ['复习：确认 / 下一题', 'Enter'],
  ['复习：记住了 / 没记住', 'Q / W'],
  ['复习：显示参考答案', '空格'],
  ['复习：填空/解答提交', 'Ctrl + Enter'],
  ['模考：末题交卷', 'Enter'],
]

function onGlobalKeydown(event) {
  if (event.key !== '?') return
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  event.preventDefault()
  shortcutsOpen.value = true
}

function onToggleThemeEvent() {
  toggleTheme(null)
}

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
  let finished = false
  const finish = () => {
    if (finished) return
    finished = true
    applyTheme(next) // 墨已盖满：此刻才真正换肤
    veil.style.transition = 'opacity .18s ease'
    veil.style.opacity = '0'
    veilTimer = setTimeout(() => {
      veil.style.display = 'none'
      veil.style.transition = ''
      themeBusy = false
    }, 200)
  }
  const grow = (t) => {
    if (finished) return
    const p = Math.min(1, (t - t0) / dur)
    const eased = 1 - Math.pow(1 - p, 3)
    veil.style.clipPath = `circle(${R * eased}px at ${x}px ${y}px)`
    if (p < 1) {
      requestAnimationFrame(grow)
      return
    }
    finish()
  }
  requestAnimationFrame(grow)
  // rAF 冻结兜底：后台标签/最小化时动画停摆，遮罩会冻在半途遮住内容
  setTimeout(finish, 1000)
}

watch(
  () => route.fullPath,
  () => {
    menuOpen.value = false
    loadRing()
  },
)

let healthTimer = 0
let examTimer = 0
let mediaHandler = null
let systemThemeHandler = null
let shortcutsHandler = null
let armTimer = 0
let veilTimer = 0

onMounted(() => {
  loadBaseData()
  loadRing()
  loadHealth()
  loadExam()
  healthTimer = setInterval(loadHealth, 30000)
  examTimer = setInterval(loadExam, 600000)
  shortcutsHandler = () => {
    shortcutsOpen.value = true
  }
  window.addEventListener('km:review-saved', loadRing)
  window.addEventListener('km:toggle-theme', onToggleThemeEvent)
  window.addEventListener('km:show-shortcuts', shortcutsHandler)
  window.addEventListener('keydown', onGlobalKeydown)
  // 窄屏：Dock 收起，改为紧凑顶栏 + 抽屉
  mq = window.matchMedia('(max-width: 1100px)')
  isNarrow.value = mq.matches
  mediaHandler = () => {
    isNarrow.value = mq.matches
  }
  mq.addEventListener?.('change', mediaHandler)
  // 从未手动选过主题就跟随系统（用户点换肤后写入 km-theme 即固定）
  if (!localStorage.getItem('km-theme')) {
    const systemMQ = window.matchMedia('(prefers-color-scheme: dark)')
    applyTheme(systemMQ.matches, false)
    systemThemeHandler = (e) => {
      if (!localStorage.getItem('km-theme')) applyTheme(e.matches, false)
    }
    systemMQ.addEventListener?.('change', systemThemeHandler)
  }
  // 开场编排（两个条件都要满足才放行 Dock / 氛围显影）：
  //   ① 启动校准动画放完 —— BootCalibration 与 AppLayout 是同一帧挂载的，
  //      不等它就会让 Dock 的入场在遮罩背后悄悄演完（用户只看到"已经摆好了"）；
  //   ② 字体样式表注入完 + 字形就绪 —— 字体 CSS 现在是异步 chunk（见 main.js），
  //      必须串在它后面读 fonts.ready，否则揭示瞬间看到的是兜底字体。
  const arm = () => document.body.classList.add('app-ready')
  const booted = document.body.classList.contains('ready')
    ? Promise.resolve()
    : new Promise((res) => window.addEventListener('km:boot-done', res, { once: true }))
  const fonts = Promise.resolve(window.__kmFontsReady)
    .catch(() => {})
    .then(() => document.fonts?.ready)
  Promise.all([booted, fonts]).then(arm)
  // 兜底看门狗故意放在 BootCalibration 自身 4200ms 之后，不抢它的收尾
  armTimer = setTimeout(arm, 4500)
})

onUnmounted(() => {
  clearInterval(healthTimer)
  clearInterval(examTimer)
  clearTimeout(armTimer)
  clearTimeout(veilTimer)
  cancelAnimationFrame(contentRaf)
  window.removeEventListener('km:review-saved', loadRing)
  window.removeEventListener('km:toggle-theme', onToggleThemeEvent)
  window.removeEventListener('km:show-shortcuts', shortcutsHandler)
  window.removeEventListener('keydown', onGlobalKeydown)
  mq?.removeEventListener?.('change', mediaHandler)
  if (systemThemeHandler) {
    window
      .matchMedia('(prefers-color-scheme: dark)')
      .removeEventListener?.('change', systemThemeHandler)
  }
})

/* ── 换页动画（JS 驱动）─────────────────────────────────────────────────
   不依赖 Vue <Transition>：连续四版实测都不可靠。
   做法：路由变化时新内容已渲染 -> 立刻给它一个**起始偏移**（内联样式），
   再用 rAF 逐步推到 0。只动 transform / opacity。
   方向由 pageDir（导航顺序决定）给出。 */
const deckInner = ref(null)
const wipeEl = ref(null)
let pageAnimRaf = 0
let contentRaf = 0

const easeOut = (p) => 1 - Math.pow(1 - p, 3)

function playPageEnter() {
  const el = deckInner.value
  if (!el) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

  // 换页墨扫：一条朱砂/墨色柔光带随新页滑入同步扫过纸面（一次性，纯 transform）。
  // 方向与页面滑入方向一致；reduced-motion 时整个函数早已 return，不会触发。
  if (wipeEl.value) {
    wipeEl.value.style.setProperty('--wipe-from', pageDir.value === 'next' ? '-103%' : '103%')
    wipeEl.value.classList.remove('run')
    void wipeEl.value.offsetWidth // 强制 reflow 重启动画
    wipeEl.value.classList.add('run')
  }

  // 方向：next = 新页在当前页右边 -> 新页从右侧进来
  const fromX = pageDir.value === 'next' ? 5.5 : -5.5
  const t0 = performance.now()
  const DUR = 420

  cancelAnimationFrame(pageAnimRaf)
  el.style.willChange = 'transform, opacity'
  // 用 rAF 而不是 setInterval(16)：后者不吃浏览器的帧时钟，
  // 高负载下会挤成两次采样、后台标签页里还会被推迟到动画结束后才收尾。
  const step = (now) => {
    const raw = Math.min(1, (now - t0) / DUR)
    const e = easeOut(raw)
    const x = fromX * (1 - e)
    const op = 0.55 + 0.45 * e
    el.style.transform = `translate3d(${x.toFixed(2)}%, 0, 0)`
    el.style.opacity = op.toFixed(3)
    if (raw < 1) {
      pageAnimRaf = requestAnimationFrame(step)
      return
    }
    el.style.transform = ''
    el.style.opacity = ''
    el.style.willChange = ''
  }
  // 必须记下这个 id：不记的话快速连切路由时上面那句 cancel 取消掉的是 0（空操作），
  // 上一段动画的循环还在跑，和新方向的循环一起写同一个 transform。
  pageAnimRaf = requestAnimationFrame(step)
}

/**
 * 路由变化后播入场动画。
 *
 * **时序是关键**（实测踩到的坑）：页面是懒加载组件 + 异步取数据，
 * `watch(route.path)` 在路由变化那一刻就触发，此时容器里还没有内容 ——
 * 动画作用在空容器上就**看不见**，等内容渲染出来时动画早已结束。
 * 所以先等容器真的有内容（首个子元素有高度）再开始，最多等 500ms。
 */
function whenContentReady(cb, deadline = 500) {
  const t0 = performance.now()
  cancelAnimationFrame(contentRaf)
  const tick = (now) => {
    const el = deckInner.value
    if (!el) return // 已卸载：deckInner 变 null，别再回调去写 style
    const child = el.firstElementChild
    const ready = child && child.getBoundingClientRect().height > 8
    if (ready || now - t0 > deadline) {
      contentRaf = 0
      cb()
      return
    }
    contentRaf = requestAnimationFrame(tick)
  }
  contentRaf = requestAnimationFrame(tick)
}

watch(
  () => route.path,
  () => {
    whenContentReady(playPageEnter)
  },
  // .page 的 CSS 入场已删（它压掉了 JS 的水平位移），首个路由也要靠这里补上
  { immediate: true },
)

onUnmounted(() => {
  cancelAnimationFrame(pageAnimRaf)
  cancelAnimationFrame(contentRaf)
})
</script>

<template>
  <div class="layout">
    <AmbientLayer />
    <ShaderBackdrop />
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

    <!-- 全局考研倒计时印（每个页面都在；窄屏改顶栏紧凑 chip） -->
    <ExamCountdown v-if="!isNarrow" :days="examDays" :date="examDate" :passed="examPassed" />

    <!-- 窄屏：紧凑顶栏 + 抽屉 -->
    <header v-if="isNarrow" class="mobile-bar">
      <router-link to="/stats" class="mb-brand">
        <span class="mb-seal">研</span>
        <b>研错本</b>
      </router-link>
      <span class="mb-ring num" :title="`今日复习 ${ringDone}/${ringTotal}`"
        >{{ ringDone }}<i>/{{ ringTotal }}</i></span
      >
      <ExamCountdown compact :days="examDays" :date="examDate" :passed="examPassed" />
      <button type="button" class="mb-btn" aria-label="搜索" @click="openPalette">
        <Icon name="search" :size="17" />
      </button>
      <button
        type="button"
        class="mb-btn"
        :aria-label="isDark ? '浅色模式' : '深色模式'"
        @click="toggleTheme"
      >
        <Icon :name="isDark ? 'sun' : 'moon'" :size="17" />
      </button>
      <button type="button" class="mb-btn" aria-label="打开菜单" @click="menuOpen = !menuOpen">
        <Icon name="menu" :size="18" />
      </button>
    </header>

    <Transition name="drawer">
      <div v-if="menuOpen" class="drawer-mask" @click="menuOpen = false"></div>
    </Transition>
    <Transition name="drawer">
      <nav v-if="menuOpen" class="drawer">
        <div class="drawer-head">
          <span class="mb-seal">研</span>
          <b class="serif">研错本</b>
          <button type="button" class="mb-btn" @click="menuOpen = false">
            <Icon name="x" :size="16" />
          </button>
        </div>
        <p class="drawer-label">工作台</p>
        <router-link
          v-for="item in PRIMARY_NAV"
          :key="item.path"
          :to="item.path"
          class="drawer-link"
          :class="{ active: activeMenu === item.path }"
        >
          <Icon :name="item.icon" :size="17" />{{ item.full }}
        </router-link>
        <p class="drawer-label">资料库</p>
        <router-link
          v-for="item in LIBRARY_NAV"
          :key="item.path"
          :to="item.path"
          class="drawer-link"
          :class="{ active: activeMenu === item.path }"
        >
          <Icon :name="item.icon" :size="17" />{{ item.full }}
        </router-link>
      </nav>
    </Transition>

    <main class="deck">
      <!--
        换页动画用 JS 驱动内联样式（不再用 <Transition>）。
        原因：Vue 的 Transition 在这套嵌套 router-view + 动态 name + 全局类名的
        组合下连续四版都不可靠（黑屏 / 上下堆叠 / 没动画）；而 JS 写内联样式
        在本环境已被证明可靠（开机动画即如此）。
      -->
      <div ref="deckInner" class="deck-inner">
        <!-- KeepAlive 只缓存六个列表页：返回时不重拉、滚动位置保留；
             数据新鲜度由各列表页的 onActivated 静默刷新负责（background load，
             不闪骨架屏）。录入/复习/编辑这类会改数据的页面刻意不缓存。 -->
        <router-view v-slot="{ Component }">
          <KeepAlive
            include="MistakeListView,VocabView,KnowledgeView,FormulaView,EssayView,PapersView"
          >
            <component :is="Component" />
          </KeepAlive>
        </router-view>
      </div>
    </main>

    <!-- 换页墨扫：一次性的朱砂/墨色柔光带扫过纸面（playPageEnter 触发） -->
    <div ref="wipeEl" class="page-wipe" aria-hidden="true"></div>

    <CommandPalette />

    <!-- 快捷键速查（? 呼出） -->
    <UiModal v-model="shortcutsOpen" title="快捷键速查" size="sm">
      <div class="shortcut-list">
        <div v-for="[label, keys] in SHORTCUT_ROWS" :key="label" class="sc-row">
          <span class="sc-label">{{ label }}</span>
          <span class="sc-keys"
            ><kbd>{{ keys }}</kbd></span
          >
        </div>
      </div>
      <template #footer>
        <span class="count-tip">在输入框打字时快捷键不生效</span>
      </template>
    </UiModal>
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
.mb-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  text-decoration: none;
  color: var(--ink);
  margin-right: auto;
}
.mb-brand b {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 800;
}
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
.mb-ring {
  font-size: 13px;
  color: var(--ink-2);
  font-weight: 700;
}
.mb-ring i {
  font-style: normal;
  font-size: 11px;
  color: var(--ink-3);
}
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
.mb-btn:hover {
  background: var(--accent-soft);
  color: var(--accent-ink);
}

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
.drawer-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  margin-bottom: 8px;
}
.drawer-head b {
  font-size: 17px;
  margin-right: auto;
  font-family: var(--font-display);
}
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
  padding: 10px 10px;
  border-radius: 10px;
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.15s var(--ease);
}
.drawer-link:hover {
  background: var(--surface-2);
  color: var(--ink);
  transform: translateX(3px);
}
.drawer-link.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
}

.drawer-enter-active,
.drawer-leave-active {
  transition:
    opacity 0.2s,
    transform 0.22s var(--ease);
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from.drawer,
.drawer-leave-to.drawer {
  transform: translateX(30px);
}

@media (max-width: 1100px) {
  .deck {
    padding: 24px 16px 40px;
  }
}

/* 快捷键速查 */
.shortcut-list {
  display: flex;
  flex-direction: column;
}
.sc-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 9px 2px;
  border-bottom: 1px dashed var(--line);
  font-size: 13px;
  color: var(--ink-2);
}
.sc-row:last-child {
  border-bottom: none;
}
.sc-label {
  min-width: 0;
}
.sc-keys kbd {
  font-family: var(--font-body);
  font-size: 11.5px;
  font-weight: 700;
  color: var(--ink);
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-bottom-width: 2px;
  border-radius: 6px;
  padding: 3px 9px;
  white-space: nowrap;
}
</style>
