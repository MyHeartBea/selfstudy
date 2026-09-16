<!--
  AtlasHome —— 首页（观测台）
  ---------------------------------------------------------------------------
  这是 v3 真正的首页。**此前这里一直是阶段 0 的占位页**（只有一行大字），
  用户现场反馈"首页不对、导航点不动、没有 atlas 的平滑动态" —— 三者都修在这里。

  对照 atlas 参考稿实现的结构与动态（按其手法在本设计系统内重建，不复制代码）：
    1. **首屏满屏**（100svh，flex column，space-between）：眉头 / 巨型标题 / 底部读数
    2. **入场错峰**：眉头 0.45s、标题两行 0.6s/0.74s、底部读数 0.85s 依次到位，
       由 `body.ready`（启动页结束）触发 —— 首页是"被揭开"，而不是和启动页一起挤出来
    3. **滚动叙事**：宣言按词块切分，随滚动逐个点亮（中文按 1-4 字词块 + 标点边界）
    4. **观测量**：真实待复习队列，每行整行可点 - 进入复习页，悬停有整行填充与位移
    5. **指针视差**：标题随指针轻微反向漂浮（rAF + lerp，只改 transform）

  数据：/api/reviews/stats + /api/stats + /api/reviews/today，三个请求并发且互不阻塞；
  任一失败都不空屏（allSettled + 逐块降级）。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, ArrowUpRight, Layers, Pencil, Sparkles } from 'lucide-vue-next'

import { reviewsApi, statsApi } from '../core/api'
import UiButton from '../ui/UiButton.vue'

const router = useRouter()

const meta = ref(null)
const stats = ref(null)
const ready = ref(false)

const reduce =
  typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/* ── 读数 ──────────────────────────────────────────────── */
const dueToday = computed(() => meta.value?.due_today ?? 0)
const streak = computed(() => meta.value?.streak_days ?? 0)
const accuracy = computed(() => Math.round(meta.value?.total_accuracy ?? 0))
const totalMistakes = computed(() => stats.value?.total_mistakes ?? 0)
const totalReviews = computed(() => meta.value?.total_reviews ?? 0)
const masteryDist = computed(() => meta.value?.mastery_distribution || [])

/* ── 观测量（前 5 条） ─────────────────────────────────── */
const queue = ref([])
const queueLoading = ref(true)

async function load() {
  const [s, st] = await Promise.allSettled([reviewsApi.stats(), statsApi.overview()])
  meta.value = s.status === 'fulfilled' ? s.value : null
  stats.value = st.status === 'fulfilled' ? st.value : null
  try {
    const today = await reviewsApi.today()
    queue.value = (Array.isArray(today) ? today : today?.items || []).slice(0, 5)
  } catch {
    queue.value = []
  } finally {
    queueLoading.value = false
  }
}

/* ── 滚动叙事：逐词点亮 ─────────────────────────────────── */
const MANIFESTO =
  '每道错题都是天上一颗星。你复习一次，它就亮一分；反复错的会红移。星图不会替你记住，但它会让遗忘变得可见。'
/** 强调词：命中即红移色（与全站"反复错 = 红移"一致） */
const ACCENT = ['星', '光', '红移', '可见']

const words = ref(
  (MANIFESTO.match(/[^，。；、]{1,4}[，。；、]?/g) || [MANIFESTO]).map((c) => {
    const bare = c.replace(/[，。；、]/g, '')
    return {
      text: c,
      on: reduce,
      opacity: reduce ? 1 : 0.09,
      acc: ACCENT.some((a) => bare.includes(a)),
    }
  }),
)
const manifestoEl = ref(null)
const drift = ref(0)

const cleanups = []

function initWordLight() {
  let ticking = false
  const update = () => {
    const el = manifestoEl.value
    if (!el) return
    const rect = el.getBoundingClientRect()
    const vh = window.innerHeight
    // 与参考稿同一映射：以 0.88vh 为起点，把"进入视口 - 完全走完"映射到 0..1
    const total = rect.height + vh * 0.55
    const p = Math.min(1, Math.max(0, (vh * 0.88 - rect.top) / total))
    const list = words.value
    list.forEach((w, i) => {
      const start = (i / list.length) * 0.78
      const local = Math.min(1, Math.max(0, (p - start) / ((1 / list.length) * 2.6)))
      w.opacity = Number((0.09 + local * 0.91).toFixed(3))
      w.on = local > 0.5
    })
    ticking = false
  }
  const onScroll = () => {
    if (ticking) return
    ticking = true
    requestAnimationFrame(update)
  }
  update()
  window.addEventListener('scroll', onScroll, { passive: true })
  window.addEventListener('resize', onScroll, { passive: true })
  cleanups.push(() => {
    window.removeEventListener('scroll', onScroll)
    window.removeEventListener('resize', onScroll)
  })
}

function initParallax() {
  let tx = 0
  let cx = 0
  let raf = 0
  const onMove = (e) => {
    tx = (e.clientX / window.innerWidth - 0.5) * 14
  }
  const loop = () => {
    cx += (tx - cx) * 0.055
    drift.value = Math.round(cx * 100) / 100
    raf = requestAnimationFrame(loop)
  }
  window.addEventListener('pointermove', onMove, { passive: true })
  raf = requestAnimationFrame(loop)
  cleanups.push(() => {
    cancelAnimationFrame(raf)
    window.removeEventListener('pointermove', onMove)
  })
}

onMounted(() => {
  // 首屏可能在启动页之前或之后挂载，两种情况都要能亮起来；
  // 启用 reduced-motion 时启动页不播，直接亮。
  if (reduce || document.body.classList.contains('ready')) {
    ready.value = true
  } else {
    const io = new MutationObserver(() => {
      if (document.body.classList.contains('ready')) {
        ready.value = true
        io.disconnect()
      }
    })
    io.observe(document.body, { attributes: true, attributeFilter: ['class'] })
    // 安全网：启动页异常时首页也必须亮，不能让整站停在暗态
    const t = setTimeout(() => (ready.value = true), 5200)
    cleanups.push(() => {
      io.disconnect()
      clearTimeout(t)
    })
  }

  if (!reduce) {
    initWordLight()
    initParallax()
  }
  load()
})

onBeforeUnmount(() => cleanups.forEach((fn) => fn()))

function go(path) {
  router.push(path)
}
</script>

<template>
  <main id="main" class="atlas" :class="{ ready }">
    <!-- ── 首屏 ──────────────────────────────────────────── -->
    <section class="hero">
      <p class="eyebrow mono">
        <span>[01]</span>
        <span class="sep" aria-hidden="true"></span>
        <span>Nocturnal Atlas · 夜航星图</span>
        <span class="sep" aria-hidden="true"></span>
        <span class="live"><i aria-hidden="true"></i>观测站在线</span>
      </p>

      <h1 class="title" :style="{ '--dx': drift + 'px' }">
        <span class="ln">未掌握的是暗</span>
        <span class="ln">已掌握的是<em>光</em></span>
      </h1>

      <div class="foot">
        <button class="scroll mono" type="button" @click="go('/review')">
          <ArrowDown :size="15" aria-hidden="true" />
          {{ dueToday > 0 ? '进入今晚的星表' : '今晚没有待复习 · 去录入一题' }}
        </button>

        <div class="read">
          <div>
            <span class="k mono">Observing</span>
            <span class="v num">{{ dueToday }}</span>
          </div>
          <div>
            <span class="k mono">Stars logged</span>
            <span class="v num">{{ totalMistakes }}</span>
          </div>
          <div>
            <span class="k mono">Reviews</span>
            <span class="v num">{{ totalReviews }}</span>
          </div>
          <div>
            <span class="k mono">Luminosity</span>
            <span class="v num">{{ accuracy }}<em>%</em></span>
          </div>
        </div>
      </div>
    </section>

    <!-- ── 宣言：逐词点亮 ────────────────────────────────── -->
    <section class="manifesto" aria-labelledby="mf-h">
      <h2 id="mf-h" class="mf-h mono">[02] 星图断面</h2>
      <p ref="manifestoEl" class="mf-text">
        <span
          v-for="(w, i) in words"
          :key="i"
          class="w"
          :class="{ on: w.on, acc: w.acc }"
          :style="{ opacity: w.opacity }"
          >{{ w.text }}</span
        >
      </p>
      <div class="mf-meta mono">
        <span>连续观测 {{ streak }} 天</span>
        <span class="sep" aria-hidden="true"></span>
        <span>掌握度分布 {{ masteryDist.length }} 档</span>
      </div>
    </section>

    <!-- ── 观测量 ────────────────────────────────────────── -->
    <section class="list" aria-labelledby="ls-h">
      <header class="ls-head">
        <h2 id="ls-h" class="ls-h mono">[03] 今晚可观测星表</h2>
        <span class="mono ls-count">{{ dueToday }} / 50 副配额</span>
      </header>

      <p v-if="queueLoading" class="mono ls-empty">正在取星表…</p>
      <p v-else-if="!queue.length" class="mono ls-empty">
        今晚没有待复习的题。可以去
        <button class="inline" type="button" @click="go('/capture')">录入一道新题</button>。
      </p>

      <div v-else class="rows">
        <button
          v-for="(q, i) in queue"
          :key="q.id"
          class="row"
          type="button"
          @click="go('/review')"
        >
          <span class="idx mono">{{ String(i + 1).padStart(2, '0') }}</span>
          <span class="q">{{ q.question }}</span>
          <span class="meta mono">
            {{ q.question_type === 'choice' ? '选择题' : '题目' }}
            <template v-if="q.review_count"> · 已复习 {{ q.review_count }} 次</template>
          </span>
          <ArrowUpRight class="arw" :size="19" aria-hidden="true" />
        </button>
      </div>
    </section>

    <!-- ── 收束 ──────────────────────────────────────────── -->
    <section class="close" aria-labelledby="cl-h">
      <h2 id="cl-h" class="mono cl-h">[04] 收束</h2>
      <p class="cl-lead">
        记住这件事没法外包。<b>但可以变得看得见</b>——看见暗在哪里，光就往哪里去。
      </p>
      <div class="cl-acts">
        <UiButton variant="solid" size="lg" @click="go('/review')">开始今晚的观测</UiButton>
        <UiButton size="lg" @click="go('/stats')">
          <Layers :size="15" aria-hidden="true" />看统计成册
        </UiButton>
        <UiButton variant="quiet" size="lg" @click="go('/capture')">
          <Pencil :size="15" aria-hidden="true" />录入一道题
        </UiButton>
      </div>
      <p class="mono cl-note">
        <Sparkles :size="13" aria-hidden="true" />
        越往后数据越准：星图的亮度来自你的每一次复习
      </p>
    </section>
  </main>
</template>

<style scoped>
.atlas {
  position: relative;
  z-index: var(--z-content);
}

/* ── 首屏 ─────────────────────────────────────────────── */
.hero {
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(88px, 13vh, 142px) var(--pad) clamp(26px, 4.5vh, 44px);
}
.eyebrow {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--ink-2);
  flex-wrap: wrap;
  opacity: 0;
  transform: translateY(14px);
  transition:
    opacity 1s var(--e-settle) 0.45s,
    transform 1s var(--e-settle) 0.45s;
}
.atlas.ready .eyebrow {
  opacity: 1;
  transform: none;
}
.eyebrow .sep {
  width: 22px;
  height: 1px;
  background: var(--line-strong);
}
.eyebrow .live {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--ink-1);
}
.eyebrow .live i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--vein);
  animation: atlas-ping 2.4s var(--e-settle) infinite;
}
@keyframes atlas-ping {
  0% {
    box-shadow: 0 0 0 0 oklch(0.775 0.098 200 / 0.5);
  }
  70% {
    box-shadow: 0 0 0 9px oklch(0.775 0.098 200 / 0);
  }
  100% {
    box-shadow: 0 0 0 0 oklch(0.775 0.098 200 / 0);
  }
}

.title {
  margin: auto 0;
  padding: clamp(20px, 4vh, 48px) 0;
  font-weight: 500;
  font-size: clamp(2.6rem, 9.4vw, 10.5rem);
  line-height: 0.88;
  letter-spacing: -0.045em;
  transform: translate3d(var(--dx, 0px), 0, 0);
  will-change: transform;
}
.title .ln {
  display: block;
  /* 逐行上浮：两行错开出现，比整块冒出来更有"揭开"感 */
  opacity: 0;
  transform: translateY(0.22em);
  transition:
    opacity 1.15s var(--e-settle),
    transform 1.35s var(--e-settle);
}
.title .ln:nth-child(1) {
  transition-delay: 0.6s;
}
.title .ln:nth-child(2) {
  transition-delay: 0.74s;
}
.atlas.ready .title .ln {
  opacity: 1;
  transform: none;
}
.title em {
  font-style: normal;
  color: var(--redshift);
  /* "光"字带发光感：与隐喻对齐（用色与模糊，不用投影） */
  text-shadow: 0 0 34px oklch(0.665 0.196 34 / 0.42);
}

.foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  opacity: 0;
  transform: translateY(16px);
  transition:
    opacity 1.1s var(--e-settle) 0.85s,
    transform 1.1s var(--e-settle) 0.85s;
}
.atlas.ready .foot {
  opacity: 1;
  transform: none;
}
.scroll {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--ink-2);
  transition: color 0.35s var(--e-settle);
}
.scroll:hover {
  color: var(--ink-0);
}
.scroll svg {
  color: var(--redshift);
  animation: atlas-bob 2.2s var(--e-settle) infinite;
}
@keyframes atlas-bob {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(4px);
  }
}
.read {
  display: flex;
  gap: clamp(16px, 3vw, 44px);
  flex-wrap: wrap;
}
.read > div {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.read .k {
  color: var(--ink-3);
}
.read .v {
  font-size: clamp(1.5rem, 3vw, 2.6rem);
  font-weight: 300;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--ink-0);
}
.read .v em {
  font-style: normal;
  font-size: 0.44em;
  color: var(--ink-2);
  margin-left: 2px;
}

/* ── 宣言 ─────────────────────────────────────────────── */
.manifesto {
  max-width: 1460px;
  margin: 0 auto;
  padding: clamp(80px, 16vh, 190px) var(--pad);
}
.mf-h {
  color: var(--ink-3);
  margin-bottom: clamp(14px, 3vh, 30px);
}
.mf-text {
  font-size: clamp(1.3rem, 3.9vw, 3.9rem);
  font-weight: 400;
  line-height: 1.18;
  letter-spacing: -0.035em;
  max-width: 22ch;
}
.w {
  display: inline-block;
  transition:
    opacity 0.28s linear,
    color 0.4s var(--e-settle);
  will-change: opacity;
}
.w.acc {
  color: var(--redshift);
}
.mf-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: clamp(20px, 4vh, 44px);
  color: var(--ink-3);
  flex-wrap: wrap;
}
.mf-meta .sep {
  width: 22px;
  height: 1px;
  background: var(--line-strong);
}

/* ── 观测星表 ─────────────────────────────────────────── */
.list {
  max-width: 1460px;
  margin: 0 auto;
  padding: 0 var(--pad) clamp(70px, 13vh, 150px);
}
.ls-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.ls-h {
  color: var(--ink-2);
}
.ls-count {
  color: var(--ink-3);
}
.ls-empty {
  padding: 26px 0;
  color: var(--ink-2);
  line-height: 1.9;
}
.inline {
  color: var(--redshift);
  border-bottom: 1px solid currentColor;
  padding-bottom: 1px;
}
.rows {
  display: flex;
  flex-direction: column;
}
/* 整行可点：事件绑在行本身（沿用 InkCard 的教训）；
   悬停整行 clip-path 填充 + 右移 + 箭头右上偏移 */
.row {
  position: relative;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto 24px;
  align-items: center;
  gap: clamp(10px, 2vw, 26px);
  padding: clamp(16px, 2.4vh, 26px) 0;
  border-bottom: 1px solid var(--line);
  text-align: left;
  isolation: isolate;
  transition: padding 0.5s var(--e-settle);
}
.row::before {
  content: '';
  position: absolute;
  inset: 0 -14px;
  z-index: -1;
  background: var(--sky-2);
  clip-path: inset(0 100% 0 0);
  transition: clip-path 0.62s var(--e-settle);
}
.row:hover::before,
.row:focus-visible::before {
  clip-path: inset(0 0 0 0);
}
.row:hover {
  padding-left: 14px;
}
.idx {
  color: var(--ink-3);
}
.q {
  font-size: clamp(0.98rem, 1.5vw, 1.22rem);
  line-height: 1.55;
  color: var(--ink-0);
  /* 长题干两行截断：列表靠"扫"不靠"读" */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta {
  color: var(--ink-3);
  white-space: nowrap;
}
.arw {
  color: var(--ink-3);
  transition:
    color 0.3s var(--e-settle),
    transform 0.45s var(--e-flare);
}
.row:hover .arw {
  color: var(--redshift);
  transform: translate(3px, -3px);
}

/* ── 收束 ─────────────────────────────────────────────── */
.close {
  max-width: 1460px;
  margin: 0 auto;
  padding: 0 var(--pad) clamp(90px, 16vh, 200px);
}
.cl-h {
  color: var(--ink-3);
  margin-bottom: clamp(12px, 2.6vh, 26px);
}
.cl-lead {
  font-size: clamp(1.15rem, 2.6vw, 2.1rem);
  line-height: 1.4;
  letter-spacing: -0.02em;
  max-width: 30ch;
  color: var(--ink-1);
}
.cl-lead b {
  color: var(--ink-0);
  font-weight: 500;
}
.cl-acts {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: clamp(22px, 4vh, 40px);
}
.cl-note {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: clamp(18px, 3vh, 32px);
  color: var(--ink-3);
}

@media (max-width: 820px) {
  .row {
    grid-template-columns: 32px minmax(0, 1fr) 20px;
    row-gap: 6px;
  }
  .row .meta {
    grid-column: 2 / 3;
  }
}
@media (prefers-reduced-motion: reduce) {
  .eyebrow,
  .foot,
  .title .ln {
    opacity: 1;
    transform: none;
    transition: none;
  }
  .w {
    transition: none;
  }
  .scroll svg,
  .eyebrow .live i {
    animation: none;
  }
  .title {
    transform: none;
  }
}
</style>
