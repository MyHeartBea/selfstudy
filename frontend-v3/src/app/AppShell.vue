<!--
  外壳导航（AppShell）
  ---------------------------------------------------------------------------
  三条要求：
   1. **滚动叙事**：向下滚动隐藏、向上滚动立即出现（读长页面时不挡视线）。
      用 rAF 节流 + 6px 阈值，避免抖动；只改 transform / opacity。
   2. **磁吸**：品牌标记与主按钮被指针"吸"过去（motion.magnetic）。
   3. **可访问**：nav 有 aria-label、当前页 aria-current、跳转到主内容的 skip link。
-->
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { reviewsApi } from '../core/api'
import { magnetic } from '../design/motion'

const route = useRoute()
const router = useRouter()
const navEl = ref(null)
const brandEl = ref(null)
const ctaEl = ref(null)

/**
 * 导航分两组：主区是每天要用的四件事，工具区是查阅类。
 * 一行塞 11 个入口会让"当前在哪"失去意义，所以宁可分两行。
 */
const LINKS = [
  // 首页 = 成册（用户要求），标签直接叫「首页」
  { to: '/', label: '首页', code: '01' },
  { to: '/review', label: '复习', code: '02' },
  { to: '/capture', label: '录入', code: '03' },
  { to: '/mistakes', label: '错题', code: '04' },
  { to: '/knowledge', label: '知识', code: '05' },
]
const LINKS_MORE = [
  { to: '/vocab', label: '生词', code: '06' },
  { to: '/formulas', label: '公式', code: '07' },
  { to: '/papers', label: '真题', code: '08' },
  { to: '/mocks', label: '模考', code: '09' },
  { to: '/subjects', label: '科目', code: '10' },
  { to: '/practice', label: '练习', code: '11' },
  { to: '/settings', label: '设置', code: '12' },
  { to: '/design', label: '规格', code: '13' },
]

let stops = []

/**
 * 右上角主按钮 —— 它此前是个**没有任何绑定的按钮**（只有样式），所以点击毫无反应。
 * 现在做成"今晚观测"的真实入口：
 *   · 有待复习 - 文案「今晚观测 · N」并直达复习页
 *   · 没有待复习 - 文案「今晚无需观测」并回首页（成册）
 * 待复习数来自 /api/reviews/stats（失败则退化为不带数字的文案，不阻塞导航）。
 */
const ctaDue = ref(null)
const ctaText = computed(() => {
  if (ctaDue.value === null) return '今晚观测'
  return ctaDue.value > 0 ? `今晚观测 · ${ctaDue.value}` : '今晚无需观测'
})
function onCta() {
  router.push(ctaDue.value ? '/review' : '/')
}
nextTick(() => {
  reviewsApi
    .stats()
    .then((s) => {
      ctaDue.value = s?.due_today ?? 0
    })
    .catch(() => {
      ctaDue.value = 0
    })
})
let ticking = false
let lastY = 0

function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    const y = window.scrollY
    const el = navEl.value
    if (el && Math.abs(y - lastY) > 6) {
      el.classList.toggle('up', y > lastY && y > 220)
      lastY = y
    }
    ticking = false
  })
}

onMounted(() => {
  lastY = window.scrollY
  window.addEventListener('scroll', onScroll, { passive: true })
  stops = [magnetic(brandEl.value, { x: 0.18, y: 0.3, max: 8 }), magnetic(ctaEl.value)]
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll)
  stops.forEach((fn) => typeof fn === 'function' && fn())
})
</script>

<template>
  <a class="skip" href="#main">跳到主内容</a>

  <header ref="navEl" class="nav" aria-label="主导航">
    <RouterLink ref="brandEl" to="/" class="brand" aria-label="回到星表">
      <span class="mark" aria-hidden="true"></span>
      <span class="name">研错本</span>
      <span class="mono reg">v3</span>
    </RouterLink>

    <nav class="links">
      <!-- 两组入口：主区（每天用）+ 工具区（查阅用）。一行塞 13 个会让"当前在哪"失去意义。 -->
      <RouterLink
        v-for="l in LINKS"
        :key="l.to"
        :to="l.to"
        class="link mono"
        :aria-current="route.path === l.to ? 'page' : undefined"
      >
        <span class="code">{{ l.code }}</span
        >{{ l.label }}
      </RouterLink>
      <span class="sep" aria-hidden="true"></span>
      <RouterLink
        v-for="l in LINKS_MORE"
        :key="l.to"
        :to="l.to"
        class="link mono more"
        :aria-current="route.path === l.to ? 'page' : undefined"
      >
        <span class="code">{{ l.code }}</span
        >{{ l.label }}
      </RouterLink>
    </nav>

    <button ref="ctaEl" class="cta" type="button" @click="onCta">
      <span>{{ ctaText }}</span>
      <svg
        viewBox="0 0 24 24"
        width="15"
        height="15"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M5 12h14" />
        <path d="m12 5 7 7-7 7" />
      </svg>
    </button>
  </header>
</template>

<style scoped>
.skip {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 90;
  padding: 10px 14px;
  background: var(--redshift);
  color: var(--sky-0);
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
}
.skip:focus {
  left: 12px;
  top: 12px;
}

.nav {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: var(--z-nav); /* 高于 --z-content，避免被页面内容覆盖（曾导致导航点不动） */
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px var(--pad);
  transition:
    transform 0.7s var(--e-settle),
    opacity 0.45s var(--e-settle);
  will-change: transform;
}
.nav.up {
  transform: translateY(-115%);
  opacity: 0;
}

/* 品牌：磁吸目标 */
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0.14em;
  transition: transform 0.35s var(--e-flare);
  will-change: transform;
}
.mark {
  width: 8px;
  height: 8px;
  background: var(--redshift);
  border-radius: 1px;
  animation: mark 5.5s var(--e-settle) infinite;
}
@keyframes mark {
  0%,
  70% {
    transform: rotate(0) scale(1);
  }
  85% {
    transform: rotate(180deg) scale(0.68);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}
.reg {
  font-size: 9px;
  vertical-align: super;
  color: var(--ink-3);
}

.links {
  display: flex;
  align-items: center;
  gap: clamp(11px, 1.6vw, 22px);
  flex-wrap: wrap;
}
/* 分组分隔：一道细竖线，不抢视觉 */
.sep {
  width: 1px;
  height: 13px;
  background: var(--line-strong);
}
/* 工具区次级配色，与主区区分但不弱化成看不清 */
.link.more {
  color: var(--ink-3);
}
.link.more:hover,
.link.more[aria-current='page'] {
  color: var(--ink-0);
}
.link {
  position: relative;
  color: var(--ink-2);
  transition: color 0.4s var(--e-settle);
}
.link .code {
  margin-right: 6px;
  color: var(--ink-3);
}
.link::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -5px;
  width: 100%;
  height: 1px;
  background: var(--redshift);
  transform: scaleX(0);
  transform-origin: right;
  transition: transform 0.6s var(--e-settle);
}
.link:hover,
.link[aria-current='page'] {
  color: var(--ink-0);
}
.link:hover::after,
.link[aria-current='page']::after {
  transform: scaleX(1);
  transform-origin: left;
}

/* 主按钮：磁吸 + 填充式悬停 */
.cta {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 10px 18px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
  position: relative;
  overflow: hidden;
  isolation: isolate;
  transition:
    color 0.45s var(--e-settle),
    border-color 0.45s var(--e-settle),
    transform 0.35s var(--e-flare);
  will-change: transform;
}
.cta::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: -1;
  background: var(--redshift);
  clip-path: inset(0 0 100% 0);
  transition: clip-path 0.6s var(--e-settle);
}
.cta:hover::before {
  clip-path: inset(0 0 0 0);
}
.cta:hover {
  color: var(--sky-0);
  border-color: var(--redshift);
}

@media (max-width: 1100px) {
  /* 窄屏不再隐藏导航（会丢功能），改为只留主区、其余进横向滚动容器 */
  .links {
    max-width: 58vw;
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;
  }
  .links::-webkit-scrollbar {
    display: none;
  }
}
@media (max-width: 700px) {
  .links {
    max-width: 46vw;
  }
  .sep,
  .link.more .code {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .nav {
    transition: none;
  }
  .mark {
    animation: none;
  }
}
</style>
