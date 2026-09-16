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
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { magnetic } from '../design/motion'

const route = useRoute()
const navEl = ref(null)
const brandEl = ref(null)
const ctaEl = ref(null)

const LINKS = [
  { to: '/', label: '星表', code: '01' },
  { to: '/review', label: '复习', code: '02' },
  { to: '/capture', label: '录入', code: '03' },
  { to: '/mistakes', label: '错题', code: '04' },
  { to: '/knowledge', label: '知识', code: '05' },
  { to: '/design', label: '规格', code: '06' },
]

let stops = []
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
    </nav>

    <button ref="ctaEl" class="cta" type="button">
      <span>今晚观测</span>
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
  z-index: var(--z-content);
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
  gap: clamp(14px, 2.6vw, 34px);
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

@media (max-width: 700px) {
  .links {
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
