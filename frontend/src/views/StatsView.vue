<script setup>
/** 学习统计 · 墨韵 2.0 Bento：英雄卡 + 瓷砖 + SVG 趋势 + 墨阶掌握度 + 热力图 + 科目分析 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { toast } from '../ui/toast'
import { sourceTypeColor, subjectColor } from '../composables/useBaseData'
import { useCountUp } from '../utils/useCountUp'
import ReviewHeatmap from '../components/ReviewHeatmap.vue'
import Icon from '../ui/Icon.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import MathText from '../components/MathText.vue'
import GlassCard from '../ui/GlassCard.vue'
import MetricTile from '../ui/MetricTile.vue'
import RingProgress from '../ui/RingProgress.vue'
import AreaChart from '../ui/AreaChart.vue'

const loading = ref(false)
const router = useRouter()
const stats = ref({
  total_mistakes: 0,
  today_new: 0,
  by_subject: [],
  by_question_type: [],
  by_source_type: [],
})
// 考研倒计时已上移到外壳（ui/ExamCountdown，每个页面都显示）
const reviewStats = ref({
  due_today: 0,
  reviewed_today: 0,
  accuracy_today: 0,
  total_accuracy: 0,
  avg_mastery: 0,
  total_reviews: 0,
  streak_days: 0,
  mastery_distribution: [],
  weakest_tags: [],
  last_7_days: [],
  by_subject: [],
})

// —— 数字滚动 ——
const nTotal = useCountUp(computed(() => stats.value.total_mistakes))
const nTodayNew = useCountUp(computed(() => stats.value.today_new))
const nDue = useCountUp(computed(() => reviewStats.value.due_today))
const nReviewed = useCountUp(computed(() => reviewStats.value.reviewed_today))
const nAccToday = useCountUp(computed(() => reviewStats.value.accuracy_today))
const nMastery = useCountUp(
  computed(() => reviewStats.value.avg_mastery),
  {
    format: (v) => (Math.round(v * 10) / 10).toFixed(1),
  },
)
const nTotalAcc = useCountUp(computed(() => reviewStats.value.total_accuracy))
const nStreak = useCountUp(computed(() => reviewStats.value.streak_days))

const ringPercent = computed(() => {
  const due = Number(reviewStats.value.due_today) || 0
  return due
    ? Math.min(100, Math.round(((Number(reviewStats.value.reviewed_today) || 0) / due) * 100))
    : 0
})

// —— 英雄卡轻倾斜（原型同款；触屏 / 减弱动效时关闭） ——
function onHeroMove(event) {
  if (!window.matchMedia('(pointer: fine)').matches) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const el = event.currentTarget
  const rect = el.getBoundingClientRect()
  const x = (event.clientX - rect.left) / rect.width - 0.5
  const y = (event.clientY - rect.top) / rect.height - 0.5
  el.style.transform = `perspective(900px) rotateY(${(x * 3.5).toFixed(2)}deg) rotateX(${(-y * 3.5).toFixed(2)}deg) translateY(-2px)`
}
function onHeroLeave(event) {
  event.currentTarget.style.transform = ''
}

// —— 7 天趋势（SVG 面积图） ——
const dayList = computed(() => reviewStats.value.last_7_days || [])
const trendLabels = computed(() => dayList.value.map((d) => d.day.slice(5)))
const trendSeries = computed(() => [
  { name: '完成次数', color: 'var(--accent)', values: dayList.value.map((d) => d.count) },
])

// —— 掌握度墨阶：六档墨色由浅入深，满级为朱砂 ——
const masterySteps = computed(() => {
  const map = new Map(
    (reviewStats.value.mastery_distribution || []).map((i) => [
      Number(i.mastery),
      Number(i.count) || 0,
    ]),
  )
  const depths = [14, 26, 42, 58, 76]
  const rows = [0, 1, 2, 3, 4, 5].map((level) => ({
    level,
    label: level === 0 ? '新题' : `${level} 级`,
    count: map.get(level) || 0,
    color:
      level === 5
        ? 'var(--accent)'
        : `color-mix(in srgb, var(--ink) ${depths[level - 1] || 14}%, var(--surface-2))`,
  }))
  const max = Math.max(1, ...rows.map((r) => r.count))
  return rows.map((r, i) => ({ ...r, percent: Math.round((r.count / max) * 100), delay: i * 70 }))
})

// —— 题型分布环形图（SVG 生长动画） ——
const TYPE_COLORS = { choice: '#2f6db3', fill: '#1a7f42', solution: '#b45309' }
const typeDonut = computed(() => {
  const items = (stats.value.by_question_type || []).filter((i) => i.count > 0)
  const total = items.reduce((sum, i) => sum + i.count, 0) || 1
  const R = 15.5
  const C = 2 * Math.PI * R
  let offset = 0
  const segs = items.map((item) => {
    const frac = item.count / total
    const seg = {
      name: item.name,
      count: item.count,
      percent: Math.round(frac * 100),
      color: TYPE_COLORS[item.question_type] || '#8f887c',
      dash: `${frac * C - 1.5} ${C - frac * C + 1.5}`,
      offset: -offset * C + C * 0.25,
    }
    offset += frac
    return seg
  })
  return { segs, total, R, C }
})
const donutGrown = ref(false)

function percentOf(count, max) {
  // max 为该列表预计算的最大值
  return Math.round((count / Math.max(1, max)) * 100)
}

const sourceMax = computed(() =>
  Math.max(1, ...(stats.value.by_source_type || []).map((s) => s.count)),
)
const subjectMax = computed(() => Math.max(1, ...stats.value.by_subject.map((s) => s.count)))
const weakMax = computed(() =>
  Math.max(1, ...(reviewStats.value.weakest_tags || []).map((w) => w.wrong_count)),
)

// —— 复习负荷预报：未来 30 天到期分布 + 逾期 ——
const forecast = ref({ overdue: 0, items: [] })
const forecastCols = computed(() => {
  const map = new Map((forecast.value.items || []).map((i) => [i.day, Number(i.count) || 0]))
  const out = []
  const today = new Date()
  for (let i = 0; i < 30; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() + i)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    out.push({
      day: key,
      count: map.get(key) || 0,
      label: i === 0 ? '今天' : i % 7 === 0 ? `${d.getMonth() + 1}/${d.getDate()}` : '',
    })
  }
  return out
})
const forecastMax = computed(() => Math.max(1, ...forecastCols.value.map((c) => c.count)))

async function loadForecast() {
  try {
    const res = await request.get('/reviews/forecast', { params: { days: 30 }, silent: true })
    forecast.value = res.data.data || { overdue: 0, items: [] }
  } catch (err) {
    // 静默失败，预报条留空即可
  }
}

// —— AI 错因周报（按天缓存，重新生成强制刷新） ——
const report = ref(null)
const reportLoading = ref(false)

async function loadWeeklyReport(force = false) {
  if (reportLoading.value) return
  reportLoading.value = true
  try {
    const res = await request.post(`/ai/weekly-report${force ? '?force=1' : ''}`, {})
    report.value = res.data.data
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    reportLoading.value = false
  }
}

// —— 模考成绩趋势 ——
const mocks = ref([])
const mockTrend = computed(() => {
  // 时间正序，取最近 12 场画折线
  const list = [...mocks.value].reverse().slice(-12)
  return list
})
const mockTrendPoints = computed(() => {
  const list = mockTrend.value
  if (list.length < 2) return ''
  return list
    .map((m, i) => {
      const p = mockPoint(i)
      return `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`
    })
    .join(' ')
})

function mockPoint(i) {
  const W = 560
  const H = 90
  const pad = 10
  const list = mockTrend.value
  return {
    x: pad + (i * (W - 2 * pad)) / Math.max(1, list.length - 1),
    y: H - pad - ((Number(list[i]?.score) || 0) / 100) * (H - 2 * pad),
  }
}

async function loadMocks() {
  try {
    const res = await request.get('/mocks', { params: { limit: 12 }, silent: true })
    mocks.value = res.data.data || []
  } catch (err) {
    // 静默失败
  }
}

// —— 科目分析：合并「题目规模」与「复习效果」两张表（按科目名关联，数据不丢） ——
const subjectMerged = computed(() => {
  const map = new Map()
  for (const s of stats.value.by_subject || []) {
    map.set(s.name, {
      name: s.name,
      subject_id: s.subject_id,
      count: Number(s.count) || 0,
      avg_difficulty: Number(s.avg_difficulty) || 0,
    })
  }
  for (const r of reviewStats.value.by_subject || []) {
    const row = map.get(r.name) || {
      name: r.name,
      subject_id: null,
      count: Number(r.mistake_count) || 0,
      avg_difficulty: 0,
    }
    row.review_count = Number(r.review_count) || 0
    row.accuracy = Number(r.accuracy) || 0
    row.wrong_count = Number(r.wrong_count) || 0
    map.set(r.name, row)
  }
  return [...map.values()]
})

async function loadStats() {
  loading.value = true
  let failed = false
  try {
    // 优先走聚合接口，回退到两个独立接口
    const res = await request.get('/dashboard', { silent: true })
    stats.value = res.data.data.stats
    reviewStats.value = res.data.data.reviews
  } catch (err) {
    try {
      // 回退请求必须 silent：不静默时拦截器会给每个失败的请求各弹一条 toast
      // （两个一起挂就是同屏两条重复报错），而 catch 吞掉后页面仍是全 0，看不出失败。
      // 用 allSettled 而不是 all —— 只要有一个接口活了就先渲染出来，别因另一个白屏。
      const [res, reviewRes] = await Promise.allSettled([
        request.get('/stats', { silent: true }),
        request.get('/reviews/stats', { silent: true }),
      ])
      if (res.status === 'fulfilled') stats.value = res.value.data.data
      if (reviewRes.status === 'fulfilled') reviewStats.value = reviewRes.value.data.data
      failed = res.status === 'rejected' || reviewRes.status === 'rejected'
    } catch (err2) {
      failed = true
    }
  } finally {
    if (failed) toast.error('统计数据加载失败，页面数字可能不完整')
    loading.value = false
    // 下一帧触发生长动画
    requestAnimationFrame(() => {
      setTimeout(() => (donutGrown.value = true), 150)
    })
  }
}

function practiceTag(tag) {
  router.push({
    path: '/review',
    query: { mode: 'curve', count: 10, tag },
  })
}

/* ── 进入状态：进入动画（BootCalibration）结束时给 body 加 .ready，
   本页据此把根元素的 .entered 打开，页面动效才播放。
   不直接用 `body.ready` 选择器承接：scoped CSS 与全局类的组合太脆（实测踩过）。 */
const entered = ref(document.body.classList.contains('ready'))
let enterObserver = null

onMounted(() => {
  if (!entered.value) {
    enterObserver = new MutationObserver(() => {
      if (document.body.classList.contains('ready')) {
        entered.value = true
        enterObserver.disconnect()
        enterObserver = null
      }
    })
    enterObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] })
  }
  loadStats()
  loadForecast()
  loadMocks()
})
onBeforeUnmount(() => {
  if (enterObserver) enterObserver.disconnect()
})
</script>

<template>
  <div class="page stats-page" :class="{ entered }">
    <div class="view-hero">
      <!-- 巨型竖排「今日」：非对称编辑网格的锚（Ink Dynasty 的竖排书法转译）。
           装饰层在左、信息在右，窄屏整体退场。 -->
      <span class="hero-mega serif" aria-hidden="true">今日</span>
      <!-- 环境字瀑（Ink Dynasty 文字瀑布的静音转译）：几枚宋体字以极低透明度
           缓落洇散。纯 CSS 合成器动画（零 rAF），reduced-motion / 窄屏隐藏。 -->
      <div class="mega-fall" aria-hidden="true">
        <span style="--fx: 6%; --fd: 96s; --fdel: -12s; --fsz: 52px; --fo: 0.05; --frot: 3deg"
          >研</span
        >
        <span style="--fx: 21%; --fd: 78s; --fdel: -51s; --fsz: 30px; --fo: 0.04; --frot: -4deg"
          >墨</span
        >
        <span style="--fx: 38%; --fd: 110s; --fdel: -30s; --fsz: 40px; --fo: 0.045; --frot: 2deg"
          >题</span
        >
        <span style="--fx: 55%; --fd: 88s; --fdel: -67s; --fsz: 26px; --fo: 0.04; --frot: -2deg"
          >错</span
        >
        <span style="--fx: 69%; --fd: 120s; --fdel: -8s; --fsz: 58px; --fo: 0.05; --frot: 4deg"
          >记</span
        >
        <span style="--fx: 84%; --fd: 82s; --fdel: -44s; --fsz: 34px; --fo: 0.04; --frot: -3deg"
          >忆</span
        >
        <span style="--fx: 93%; --fd: 102s; --fdel: -72s; --fsz: 44px; --fo: 0.045; --frot: 2deg"
          >纸</span
        >
      </div>
      <div class="view-hero-copy">
        <div class="view-kicker">Learning Analytics</div>
        <!-- 标题逐行揭示：外层做遮罩，内层做位移（参考稿的 line / line__i 手法） -->
        <h2 class="ttl">
          <span class="ttl-line"><span class="ttl-i">学习统计</span></span>
        </h2>
        <p class="view-desc" data-reveal-words>用数据看复习节奏，找到下一轮该攻克的薄弱点。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="primary" data-magnetic @click="router.push('/review')">
          <Icon name="refresh" :size="15" />
          开始今日复习
        </UiButton>
      </div>
    </div>

    <!-- 顶部区：英雄卡 + 两张瓷砖（子网格两行强制等高，卡片对齐） -->
    <div class="bento-top">
      <GlassCard
        class="b-hero km-live"
        :hover="false"
        style="--h: 12"
        @mousemove="onHeroMove"
        @mouseleave="onHeroLeave"
      >
        <!-- 复合悬停的装饰层（幽灵序号 / 四角 / 扫描线 / 顶边标尺） -->
        <span class="km-live__ghost" aria-hidden="true">今</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <span class="hero-seal" aria-hidden="true">今</span>
        <div class="hero-bg" aria-hidden="true" data-parallax="48"></div>
        <span
          v-if="reviewStats.streak_days"
          class="streak-chip"
          :title="`最长连续纪录见「连续复习」`"
        >
          <Icon name="flame" :size="14" />
          连续 <b class="num km-num">{{ nStreak }}</b> 天
        </span>
        <div class="hero-label"><Icon name="clock" :size="15" /> 今日待复习</div>
        <div class="hero-body">
          <div class="hero-left">
            <div class="hero-value num km-num">{{ nDue }}</div>
            <div class="hero-delta">
              今日新增 <b>{{ nTodayNew }}</b> 题 · 新错题优先
            </div>
            <div class="hero-chips">
              <span class="h-chip"
                ><Icon name="target" :size="13" />今日正确率
                <b class="num km-num">{{ nAccToday }}<i>%</i></b></span
              >
              <span class="h-chip"
                ><i class="ink-lvl" :style="{ '--lvl': nMastery }" aria-hidden="true"></i>平均掌握度
                <b class="num km-num">{{ nMastery }}</b></span
              >
            </div>
            <UiButton variant="primary" class="hero-cta" @click="router.push('/review')">
              开始今日复习
              <Icon name="chevron-right" :size="15" />
            </UiButton>
          </div>
          <RingProgress :percentage="ringPercent">
            <div class="ring-center-text">
              <b class="num km-num">{{ nReviewed }}/{{ reviewStats.due_today }}</b>
              <span>今日已完成</span>
            </div>
          </RingProgress>
        </div>
      </GlassCard>

      <GlassCard class="b-tile km-live">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">03</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <MetricTile icon="layers" :value="nTotal" label="累计错题" tone="accent" />
      </GlassCard>
      <GlassCard class="b-tile km-live">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">04</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <MetricTile
          icon="chart"
          :value="nTotalAcc"
          unit="%"
          label="累计正确率 · 总复习"
          tone="teal"
        />
      </GlassCard>
    </div>

    <!-- 主 Bento：趋势 + 墨阶 / 热力图 + 薄弱点 -->
    <div class="bento" data-parallax="36">
      <GlassCard class="span2 km-live">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">05</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <div class="panel-head">
          <h3 class="panel-title" data-reveal-lines>复习趋势</h3>
          <span class="cap">近 7 天完成次数（描边生长）</span>
        </div>
        <AreaChart
          v-if="dayList.length"
          :labels="trendLabels"
          :series="trendSeries"
          :height="200"
        />
        <UiEmpty v-else text="近 7 天暂无复习记录" icon="chart" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title" data-reveal-lines>掌握度墨阶</h3>
        <p class="cap" data-reveal-words>{{ stats.total_mistakes }} 道错题 · 墨色越深掌握越牢</p>
        <div class="m-steps" data-grow="steps">
          <div
            v-for="s in masterySteps"
            :key="s.level"
            class="m-step"
            :style="{ '--d': s.delay + 'ms' }"
          >
            <b class="num km-num">{{ s.count }}</b>
            <div class="m-pill">
              <i
                class="m-fill"
                :style="{ '--h': s.percent, '--mcol': s.color, animationDelay: s.delay + 'ms' }"
              ></i>
            </div>
            <span class="m-label">{{ s.label }}</span>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title" data-reveal-lines>薄弱知识点</h3>
        <p class="cap">按累计答错排序 · 点击直通练习</p>
        <div v-if="reviewStats.weakest_tags.length" class="weak-list km-list">
          <button
            v-for="(row, i) in reviewStats.weakest_tags"
            :key="row.tag_name"
            type="button"
            class="weak-item km-item"
            @click="practiceTag(row.tag_name)"
          >
            <span class="w-rank num km-num">{{ i + 1 }}</span>
            <span class="w-name">
              <b>{{ row.tag_name }}</b>
              <span>错 {{ row.wrong_count }} 次 · 关联 {{ row.mistake_count }} 题</span>
            </span>
            <span class="w-bar"
              ><span class="w-track"
                ><i :style="{ width: percentOf(row.wrong_count, weakMax) + '%' }"></i></span
            ></span>
          </button>
        </div>
        <UiEmpty v-else text="暂无薄弱知识点" icon="target" />
        <UiButton
          v-if="reviewStats.weakest_tags.length"
          variant="outline"
          block
          size="sm"
          class="weak-more"
          @click="practiceTag(reviewStats.weakest_tags[0].tag_name)"
        >
          直通薄弱练习
        </UiButton>
      </GlassCard>

      <GlassCard class="span2 km-live">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">06</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <div class="panel-head">
          <h3 class="panel-title" data-reveal-lines>复习热力图</h3>
          <UiButton size="sm" variant="ghost" @click="router.push('/review')">
            去复习，点亮今天
          </UiButton>
        </div>
        <ReviewHeatmap :days="119" data-reveal-lines />
      </GlassCard>

      <!-- 复习负荷预报 -->
      <GlassCard class="span3 fc-strip km-live" :pad="false" :hover="false">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">07</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <div class="fc-head">
          <h3 class="panel-title" data-reveal-lines>复习负荷预报</h3>
          <span class="cap">未来 30 天到期分布，哪天堆多了提前匀开</span>
          <span v-if="forecast.overdue" class="fc-overdue"
            >逾期 <b class="num km-num">{{ forecast.overdue }}</b> 题</span
          >
        </div>
        <div class="fc-bars" data-grow="bars">
          <div
            v-for="c in forecastCols"
            :key="c.day"
            class="fc-col"
            :title="`${c.day}：到期 ${c.count} 题`"
          >
            <i
              :class="{ peak: c.count === forecastMax && c.count > 0, today: c.label === '今天' }"
              :style="{
                height:
                  (c.count ? Math.max(6, Math.round((c.count / forecastMax) * 64)) : 4) + 'px',
              }"
            ></i>
            <span class="fc-label num km-num">{{ c.label }}</span>
          </div>
        </div>
      </GlassCard>

      <!-- AI 错因周报 -->
      <GlassCard class="span3 report-strip km-live" :hover="false">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">08</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <div class="rp-head">
          <div>
            <h3 class="panel-title" data-reveal-lines>AI 错因周报</h3>
            <p class="cap">近 7 天答错题目按错因聚类，给出针对性训练建议</p>
          </div>
          <div class="rp-actions">
            <span v-if="report && !report.empty && report.cached" class="rp-cached"
              >今日已生成 · 缓存</span
            >
            <UiButton
              variant="primary"
              size="sm"
              :loading="reportLoading"
              @click="loadWeeklyReport(!report || report.cached)"
            >
              <Icon name="sparkles" :size="14" />
              {{ report ? '重新生成' : '生成本周报告' }}
            </UiButton>
          </div>
        </div>
        <p v-if="reportLoading" class="rp-hint">AI 正在聚类分析近 7 天的错题…（约 10-30 秒）</p>
        <p v-else-if="report?.empty" class="rp-hint">{{ report.message }}</p>
        <template v-else-if="report">
          <p class="rp-summary"><MathText :text="report.summary" /></p>
          <div class="rp-clusters">
            <div v-for="(c, i) in report.clusters" :key="i" class="rp-cluster">
              <span class="rp-rank num km-num">{{ i + 1 }}</span>
              <div class="rp-body">
                <div class="rp-line">
                  <b class="serif">{{ c.cause }}</b>
                  <span class="rp-count num km-num">{{ c.count }} 题</span>
                </div>
                <p class="rp-advice"><MathText :text="c.advice" /></p>
                <div v-if="c.tags && c.tags.length" class="rp-tags">
                  <UiTag
                    v-for="t in c.tags"
                    :key="t"
                    size="sm"
                    color="var(--gold)"
                    soft
                    clickable
                    @click="practiceTag(t)"
                    >{{ t }}</UiTag
                  >
                </div>
              </div>
            </div>
          </div>
        </template>
      </GlassCard>

      <!-- 模考成绩趋势 -->
      <GlassCard class="span3 mock-strip" :pad="false" :hover="false">
        <!-- 复合悬停装饰层 -->
        <span class="km-live__ghost" aria-hidden="true">09</span>
        <span class="km-live__rule" aria-hidden="true"></span>
        <span class="km-live__corner tl" aria-hidden="true"></span>
        <span class="km-live__corner tr" aria-hidden="true"></span>
        <span class="km-live__corner bl" aria-hidden="true"></span>
        <span class="km-live__corner br" aria-hidden="true"></span>
        <span class="km-live__scan" aria-hidden="true"></span>
        <div class="fc-head">
          <h3 class="panel-title" data-reveal-lines>模考成绩趋势</h3>
          <span class="cap">最近 {{ mockTrend.length }} 场 · 交卷自动存档</span>
        </div>
        <div v-if="mockTrend.length >= 2" class="mk-chart" data-grow="chart">
          <svg
            viewBox="0 0 560 90"
            width="100%"
            style="display: block"
            role="img"
            aria-label="模考分数趋势"
          >
            <path
              :d="mockTrendPoints"
              fill="none"
              stroke="var(--accent)"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle
              v-for="(m, i) in mockTrend"
              :key="i"
              :cx="mockPoint(i).x"
              :cy="mockPoint(i).y"
              r="3.5"
              fill="var(--surface)"
              stroke="var(--accent)"
              stroke-width="2.2"
            />
          </svg>
        </div>
        <div v-if="mockTrend.length" class="mk-meta">
          <span v-for="(m, i) in mockTrend" :key="i" class="mk-chip num km-num">
            {{ m.exam_year || '—' }} · {{ m.score }} 分 · {{ m.correct }}/{{ m.total }}
          </span>
        </div>
        <p v-else class="cap mk-empty">
          还没有模考存档——去「自主练习 - 真题模考」打一场，成绩会自动记到这里。
        </p>
      </GlassCard>
    </div>

    <!-- 分布 -->
    <div class="grid-2">
      <GlassCard>
        <h3 class="panel-title" data-reveal-lines>题型分布</h3>
        <div v-if="typeDonut.segs.length" class="donut-wrap">
          <svg class="donut" viewBox="0 0 40 40" role="img" aria-label="题型分布环形图">
            <circle class="donut-track" cx="20" cy="20" :r="typeDonut.R" />
            <circle
              v-for="seg in typeDonut.segs"
              :key="seg.name"
              class="donut-seg"
              :stroke="seg.color"
              cx="20"
              cy="20"
              :r="typeDonut.R"
              :stroke-dasharray="donutGrown ? seg.dash : `0 ${typeDonut.C}`"
              :stroke-dashoffset="seg.offset"
            />
          </svg>
          <div class="donut-center">
            <div class="donut-total num km-num">{{ typeDonut.total }}</div>
            <div class="donut-total-label">总题数</div>
          </div>
          <div class="donut-legend">
            <div v-for="seg in typeDonut.segs" :key="seg.name" class="legend-item">
              <span class="legend-dot" :style="{ background: seg.color }"></span>
              <span class="legend-name">{{ seg.name }}</span>
              <span class="legend-num num km-num">{{ seg.count }}</span>
              <span class="legend-pct num km-num">{{ seg.percent }}%</span>
            </div>
          </div>
        </div>
        <UiEmpty v-else text="暂无题型数据" icon="list" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title" data-reveal-lines>题目来源分布</h3>
        <div v-if="stats.by_source_type && stats.by_source_type.length">
          <div v-for="s in stats.by_source_type" :key="s.source_type" class="src-row">
            <span class="s-name">{{ s.name }}</span>
            <span class="src-track"
              ><i
                :style="{
                  width: percentOf(s.count, sourceMax) + '%',
                  background: sourceTypeColor(s.source_type),
                }"
              ></i
            ></span>
            <span class="s-nums num km-num">{{ s.count }} 题</span>
          </div>
        </div>
        <UiEmpty v-else text="暂无题目来源数据" icon="tag" />
      </GlassCard>
    </div>

    <!-- 科目分析：规模 × 效果 合并一张图 -->
    <GlassCard class="block-card">
      <div class="panel-head">
        <h3 class="panel-title" data-reveal-lines>科目分析</h3>
        <span class="cap">错题规模 × 复习效果 · 墨条越长征题越多</span>
      </div>
      <div v-if="subjectMerged.length" class="subj-list">
        <div v-for="s in subjectMerged" :key="s.name" class="subj-row">
          <span class="s-name">{{ s.name }}</span>
          <span class="s-bar">
            <i
              class="s-fill"
              :style="{
                '--w': percentOf(s.count, subjectMax),
                '--scol': s.subject_id ? subjectColor(s.subject_id) : 'var(--ink-3)',
                animationDelay: '80ms',
              }"
            ></i>
          </span>
          <span class="s-nums num km-num">
            <b>{{ s.count }}</b> 题
            <em>复习 {{ s.review_count || 0 }}</em>
            <em :class="{ good: (s.accuracy || 0) >= 70, warn: (s.accuracy || 0) < 50 }"
              >{{ s.accuracy || 0 }}%</em
            >
            <em>错 {{ s.wrong_count || 0 }}</em>
            <em v-if="s.avg_difficulty > 0">均难 {{ s.avg_difficulty.toFixed(1) }}</em>
          </span>
        </div>
      </div>
      <UiEmpty v-else text="暂无科目数据" icon="book" />
    </GlassCard>
  </div>
</template>

<style scoped>
/* ---------- 顶部区（子网格：两行强制等高 - 卡片对齐） ---------- */
.bento-top {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  grid-template-rows: repeat(2, minmax(158px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.b-tile {
  display: flex;
}
.b-tile :deep(.gcard-body) {
  flex: 1;
  display: flex;
  align-items: center;
}

/* ---------- 主 Bento ---------- */
.bento {
  display: grid;
  /* 非对称杂志网格：三列刻意不等宽（宽-窄-中），
     行序也交错（宽卡左右轮换），打破"三等分对称"的模板感 */
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1.2fr);
  gap: 16px;
  margin-bottom: 16px;
}
.span2 {
  grid-column: span 2;
}
.span3 {
  grid-column: span 3;
}

/* 英雄卡 */
.b-hero {
  grid-row: 1 / 3;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s var(--ease);
}
.hero-seal {
  position: absolute;
  right: -6px;
  bottom: -34px;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 168px;
  line-height: 1;
  color: var(--accent);
  opacity: 0.07;
  transform: rotate(6deg);
  pointer-events: none;
  user-select: none;
}
.hero-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  /* 全幅覆盖：旧版 420px 局部晕在宽屏上只染到卡片一角，
     未染到的区域读起来像"框中框"（用户实测反馈）。
     改为大半径百分比晕 + 整卡基染，整张卡是一个连续的墨面。 */
  background:
    radial-gradient(
      125% 125% at 10% -6%,
      color-mix(in srgb, var(--accent) 22%, transparent),
      transparent 64%
    ),
    radial-gradient(
      110% 115% at 106% 108%,
      color-mix(in srgb, var(--teal) 18%, transparent),
      transparent 58%
    ),
    linear-gradient(
      160deg,
      color-mix(in srgb, var(--accent) 10%, transparent),
      transparent 46%,
      color-mix(in srgb, var(--teal) 8%, transparent)
    );
}
.streak-chip {
  position: absolute;
  top: 22px;
  right: 24px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 15px;
  border-radius: 999px;
  background: var(--gold-soft);
  color: var(--gold);
  font-size: 13px;
  font-weight: 700;
}
.streak-chip svg {
  animation: flame-flicker 2.2s ease-in-out infinite;
}
@keyframes flame-flicker {
  0%,
  100% {
    transform: scale(1) rotate(0deg);
  }
  30% {
    transform: scale(1.14) rotate(-4deg);
  }
  60% {
    transform: scale(1.06) rotate(3deg);
  }
}
.hero-label {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  color: var(--ink-2);
}
.hero-label :deep(svg) {
  color: var(--accent);
}
.hero-body {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 10px;
}
.hero-left {
  min-width: 0;
}
/* 巨型竖排「今日」：编辑式非对称锚点，完整立于页首左侧 */
.hero-mega {
  position: absolute;
  left: 0;
  top: 50%;
  translate: 0 -50%;
  writing-mode: vertical-rl;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: calc(var(--fs-mega) * 0.78);
  line-height: 0.9;
  letter-spacing: 0.1em;
  color: var(--ink);
  opacity: 0.075;
  pointer-events: none;
  user-select: none;
  /* 纸下有字：鼠标扫过页首时水印浮出来一点（用父级 hover 触发，
     mega 自身 pointer-events:none 不拦任何点击） */
  transition: opacity var(--dur-4) var(--ease-enter);
}
.view-hero:hover .hero-mega {
  opacity: 0.11;
}
/* 巨字入场 = 笔锋显影：自上而下 clip 揭示 + 墨晕聚焦（vertical-rl 的
   "书写方向"就是自上而下）。fill 用 backwards：播完释放回自然样式，
   上面的 hover 浮出过渡才不会被动画末帧钉死。reduced-motion 不播。 */
@media (prefers-reduced-motion: no-preference) {
  .hero-mega {
    animation: mega-reveal var(--dur-5) var(--ease-enter) var(--stagger-2) backwards;
  }
}
@keyframes mega-reveal {
  from {
    opacity: 0;
    filter: blur(8px);
    clip-path: inset(0 0 100% 0);
  }
  to {
    opacity: 0.075;
    filter: blur(0);
    clip-path: inset(0 0 -0.12em 0);
  }
}

/* 环境字瀑：整层自裁切，字从上缘落入、下缘洇出。压在页首内容之下
   （z-index 0，内容层 z-index 1），pointer-events 全免。 */
.mega-fall {
  position: absolute;
  inset: 0;
  overflow: hidden;
  z-index: 0;
  pointer-events: none;
}
.mega-fall span {
  position: absolute;
  top: 0;
  left: var(--fx);
  font-family: var(--font-display);
  font-weight: 900;
  font-size: var(--fsz);
  line-height: 1;
  color: var(--ink);
  opacity: 0;
  user-select: none;
}
.stats-page .view-hero > .view-hero-copy,
.stats-page .view-hero > .header-actions {
  position: relative;
  z-index: 1;
}
@media (prefers-reduced-motion: no-preference) {
  .mega-fall span {
    animation: mega-fall var(--fd) linear var(--fdel) infinite;
  }
}
@keyframes mega-fall {
  0% {
    transform: translateY(-60px) rotate(var(--frot, 0deg));
    opacity: 0;
  }
  10% {
    opacity: var(--fo);
  }
  80% {
    opacity: var(--fo);
  }
  100% {
    transform: translateY(330px) rotate(calc(var(--frot, 0deg) * -1));
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce), (max-width: 900px) {
  .mega-fall {
    display: none;
  }
}
.stats-page .view-hero {
  /* 给竖排大字让位：信息块整体右移（窄屏由下方媒体查询收回） */
  padding-left: clamp(0px, 15vw, 236px);
  min-height: calc(var(--fs-mega) * 1.62);
}
@media (max-width: 900px) {
  .hero-mega {
    display: none;
  }
  .stats-page .view-hero {
    padding-left: 0;
    min-height: 0;
  }
}
/* 掌握度墨滴：一滴墨的浓度 = 平均掌握度（「记忆即墨」的数据语义化） */
.ink-lvl {
  width: 11px;
  height: 11px;
  border-radius: 50% 50% 50% 4px;
  background: var(--ink);
  opacity: max(0.14, var(--lvl, 0));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ink) 20%, transparent);
  flex: none;
}
.hero-value {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 72px;
  line-height: 1.05;
  color: var(--accent);
  letter-spacing: -0.02em;
  text-shadow: 0 2px 24px color-mix(in srgb, var(--accent) 22%, transparent);
  /* 英雄区唯一动效锚点：大数字墨晕显影（从虚到实），与 useCountUp 的
     数字滚动叠加 —— easylog 案例的结论：动效要讲概念（今日分量落纸），
     而不是再添一个装饰。一次性播放，reduced-motion 由全局规则压停。 */
  animation: ink-bloom var(--dur-5) var(--ease-enter) 0.12s both;
}
@keyframes ink-bloom {
  from {
    opacity: 0;
    filter: blur(10px);
    transform: scale(0.94);
  }
  to {
    opacity: 1;
    filter: blur(0);
    transform: scale(1);
  }
}
.hero-delta {
  font-size: 13px;
  color: var(--ink-3);
  margin: 6px 0 14px;
}
.hero-delta b {
  color: var(--green);
  font-weight: 700;
}
.hero-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.h-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 13px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 12.5px;
  color: var(--ink-2);
  white-space: nowrap;
}
.h-chip svg {
  color: var(--accent);
}
.h-chip b {
  color: var(--ink);
  font-weight: 800;
}
.h-chip i {
  font-style: normal;
  font-size: 11px;
  color: var(--ink-3);
}
.ring-center-text b {
  display: block;
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 900;
  line-height: 1.1;
}
.ring-center-text span {
  display: block;
  font-size: 11.5px;
  color: var(--ink-3);
  margin-top: 2px;
}

/* ---------- 墨阶掌握度 ---------- */
.m-steps {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  margin-top: 16px;
  height: 172px;
}
.m-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-height: 0;
}
.m-step > b {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 16px;
}
.m-pill {
  width: 100%;
  flex: 1;
  border-radius: 9px;
  background: color-mix(in srgb, var(--ink) 4%, var(--surface-2));
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.m-fill {
  display: block;
  width: 100%;
  height: calc(var(--h) * 1%);
  border-radius: 9px;
  background: var(--mcol);
  transform-origin: bottom;
  animation: m-grow 0.9s var(--spring) both;
}
@keyframes m-grow {
  from {
    transform: scaleY(0);
  }
  to {
    transform: scaleY(1);
  }
}
.m-label {
  font-size: 11.5px;
  color: var(--ink-3);
  white-space: nowrap;
}

/* ---------- 面板通用 ---------- */
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.panel-title {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  margin-bottom: 4px;
}
.cap {
  font-size: 12.5px;
  color: var(--ink-3);
}

/* ---------- 薄弱点列表 ---------- */
.weak-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 10px;
  /* 与热力图卡同排时限制高度，避免热力图卡被撑出大片空白 */
  max-height: 460px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.weak-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 12px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.18s var(--ease),
    transform 0.18s var(--ease);
}
.weak-item:hover {
  background: var(--accent-soft);
  transform: translateX(4px);
}
.w-rank {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  flex: none;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  background: var(--surface-2);
  color: var(--ink-3);
  transition: all 0.2s var(--spring);
}
.weak-item:hover .w-rank {
  transform: rotate(-8deg) scale(1.12);
  background: var(--accent-soft);
  color: var(--accent);
}
.w-name {
  flex: 1;
  min-width: 0;
}
.w-name b {
  font-size: 13.5px;
  font-weight: 600;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--ink);
}
.w-name span {
  font-size: 11.5px;
  color: var(--ink-3);
}
.w-bar {
  width: 64px;
  flex: none;
}
.w-track {
  display: block;
  height: 6px;
  border-radius: 99px;
  background: var(--surface-2);
  overflow: hidden;
}
.w-track i {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: var(--accent);
  transition: width 1.1s var(--spring);
}
.weak-more {
  margin-top: 12px;
}

/* 复习负荷预报条 */
.fc-strip {
  overflow: hidden;
}
.fc-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  padding: 16px 22px 0;
}
.fc-overdue {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--red);
  background: var(--red-soft);
  padding: 3px 12px;
  border-radius: 999px;
}
.fc-overdue b {
  font-weight: 800;
}
.fc-bars {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  padding: 14px 22px 10px;
}
.fc-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.fc-col i {
  display: block;
  width: 100%;
  max-width: 24px;
  border-radius: 4px 4px 2px 2px;
  background: color-mix(in srgb, var(--accent) 40%, var(--surface-2));
  transition: height 0.8s var(--spring);
}
.fc-col i.today {
  background: var(--accent-grad);
  box-shadow: 0 0 0 1px var(--accent-ring);
}
.fc-col i.peak {
  background: var(--accent);
}
.fc-label {
  font-size: 10px;
  color: var(--ink-3);
  height: 14px;
  white-space: nowrap;
}

/* AI 错因周报 */
.rp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.rp-hint {
  margin: 14px 0 2px;
  font-size: 13px;
  color: var(--ink-3);
}
.rp-summary {
  margin: 14px 0 2px;
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: var(--accent-soft);
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink);
}
.rp-clusters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.rp-cluster {
  display: flex;
  gap: 11px;
  padding: 12px 14px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
}
.rp-rank {
  width: 24px;
  height: 24px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 800;
  font-size: 12px;
}
.rp-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.rp-line b {
  font-size: 15px;
  color: var(--ink);
}
.rp-count {
  font-size: 12px;
  color: var(--accent-ink);
  font-weight: 700;
}
.rp-advice {
  margin: 4px 0 6px;
  font-size: 12.8px;
  line-height: 1.8;
  color: var(--ink-2);
}
.rp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.rp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.rp-cached {
  font-size: 12px;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 3px 11px;
  border-radius: 999px;
}

/* 模考趋势条 */
.mk-chart {
  padding: 12px 22px 2px;
}
.mk-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 6px 22px 16px;
}
.mk-chip {
  font-size: 11.5px;
  color: var(--ink-2);
  background: var(--surface-2);
  padding: 3px 11px;
  border-radius: 999px;
}
.mk-empty {
  padding: 0 22px 16px;
  margin: 0;
}

/* ---------- 下部布局 ---------- */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.block-card {
  margin-bottom: 16px;
}

/* ---------- 环形图 ---------- */
.donut-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 22px;
}
.donut {
  width: 148px;
  height: 148px;
  flex: none;
}
.donut-track {
  fill: none;
  stroke: var(--surface-2);
  stroke-width: 6;
}
.donut-seg {
  fill: none;
  stroke-width: 6;
  stroke-linecap: butt;
  transition: stroke-dasharray 0.9s var(--spring);
}
.donut-center {
  position: absolute;
  left: 0;
  top: 0;
  width: 148px;
  height: 148px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.donut-total {
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
}
.donut-total-label {
  font-size: 10.5px;
  color: var(--ink-3);
  margin-top: 3px;
  letter-spacing: 0.08em;
}
.donut-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
  min-width: 0;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 3px;
  flex: none;
}
.legend-name {
  color: var(--ink-2);
}
.legend-num {
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.legend-pct {
  color: var(--ink-3);
  font-size: 12px;
  width: 38px;
  text-align: right;
}

/* ---------- 来源 / 科目条形行 ---------- */
.src-row,
.subj-row {
  display: grid;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}
.src-row {
  grid-template-columns: 150px 1fr 64px;
}
.subj-row {
  grid-template-columns: 150px 1fr minmax(300px, auto);
  transition: background 0.16s var(--ease);
  border-radius: 10px;
  padding-left: 8px;
  padding-right: 8px;
}
.subj-row:hover {
  background: var(--accent-soft);
}
.s-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.src-track {
  display: block;
  height: 9px;
  border-radius: 99px;
  background: var(--surface-2);
  overflow: hidden;
}
.src-track i {
  display: block;
  height: 100%;
  border-radius: 99px;
  transition: width 1.1s var(--spring);
}
.s-bar {
  display: block;
  height: 12px;
  border-radius: 99px;
  background: var(--surface-2);
  overflow: hidden;
}
.s-fill {
  display: block;
  height: 100%;
  width: calc(var(--w) * 1%);
  border-radius: 99px;
  background: linear-gradient(90deg, var(--scol), color-mix(in srgb, var(--scol) 45%, transparent));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: width 1.1s var(--spring);
}
.s-nums {
  font-size: 12px;
  color: var(--ink-3);
  text-align: right;
  white-space: nowrap;
}
.subj-row .s-nums em {
  font-style: normal;
  margin-left: 12px;
}
.subj-row .s-nums b {
  font-family: var(--font-display);
  font-size: 15px;
  color: var(--ink);
}
.subj-row .s-nums .good {
  color: var(--green);
  font-weight: 700;
}
.subj-row .s-nums .warn {
  color: var(--red);
  font-weight: 700;
}

@media (max-width: 1100px) {
  .bento {
    grid-template-columns: repeat(2, 1fr);
  }
  /* 两列网格下通栏卡只跨两列，避免撑出隐式第三列 */
  .span3 {
    grid-column: span 2;
  }
}
@media (max-width: 860px) {
  .bento {
    grid-template-columns: 1fr;
  }
  .span2,
  .span3 {
    grid-column: span 1;
  }
  .bento-top {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }
  .b-hero {
    grid-row: auto;
  }
  .b-hero .hero-body {
    flex-direction: column;
    align-items: flex-start;
  }
  .hero-value {
    font-size: 56px;
  }
  .grid-2 {
    grid-template-columns: 1fr;
  }
  .subj-row {
    grid-template-columns: 96px 1fr;
  }
  .subj-row .s-nums {
    grid-column: 1 / 3;
    text-align: left;
  }
  .subj-row .s-nums em:first-child {
    margin-left: 0;
  }
}
/* ── 进入动画（由进入动画结束时给根元素加的 .entered 触发）─────────────
   与进入动画的分工：进入动画负责"整块向上抽走"，页面只负责"抽走后错峰到位"。
   body:not(.ready) 时元素保持隐藏 —— 进入动画还在播时页面不会提前露脸。 */
.stats-page .view-hero,
.stats-page .bento-top {
  opacity: 0;
  transform: translateY(16px);
  transition:
    opacity 0.9s var(--ease),
    transform 1.05s var(--spring, var(--ease));
}
/* 英雄卡是视觉主角：位移稍大、带极轻的缩放 */
.stats-page .b-hero {
  opacity: 0;
  transform: translateY(22px) scale(0.985);
  transition:
    opacity 1s var(--ease),
    transform 1.2s var(--spring, var(--ease));
}
.stats-page.entered .view-hero,
.stats-page.entered .bento-top,
.stats-page.entered .b-hero {
  opacity: 1;
  transform: none;
}
/* 错峰：先标题、再 Bento 区（英雄卡随 Bento 一起，它是该区第一块） */
.stats-page.entered .view-hero {
  transition-delay: 0.02s;
}
.stats-page.entered .bento-top {
  transition-delay: 0.14s;
}

@media (prefers-reduced-motion: reduce) {
  .stats-page .view-hero,
  .stats-page .bento-top,
  .stats-page .b-hero {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
/* ── 首屏排版尺度（学习参考稿：把层级拉开）─────────────────────────────
   只改字号/字距/层级，不动字体族与配色 —— 保持 v2 的一致性。
   参考稿的量级是 clamp(2.4rem, 9.2vw, 10rem) + line-height .88；
   v2 有侧栏与工具栏、且首屏是 Bento（不是满屏单标题），照抄会撑破，
   所以按实际可用宽度收敛到 6.4vw / 5.6rem。 */
.stats-page .view-hero-copy h2 {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: clamp(2.2rem, 6.4vw, 5.6rem);
  line-height: 1.02;
  letter-spacing: -0.035em;
  margin: 6px 0 10px;
}
/* 眉头：极小 + 大字距大写（参考稿的 eyebrow 手法） */
.stats-page .view-kicker {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--accent);
}
.stats-page .view-desc {
  font-size: clamp(0.92rem, 1.1vw, 1.06rem);
  line-height: 1.75;
  max-width: 44ch;
  color: var(--ink-2);
}

/* 英雄读数：放大到参考稿的量级（它用 clamp(1.5rem,3vw,2.6rem)） */
.stats-page .hero-value {
  font-size: clamp(3rem, 7vw, 6.4rem);
  line-height: 0.9;
  letter-spacing: -0.04em;
}
/* 瓷砖里的读数：同样放大，但比英雄卡低一级（层级要有主次） */
.stats-page .b-tile .num {
  font-size: clamp(1.5rem, 2.6vw, 2.4rem);
  line-height: 1;
  letter-spacing: -0.03em;
}
/* 区块标题：参考稿是等宽小字 + 分隔线，比卡片大标题更克制 */
.stats-page .panel-title,
.stats-page .panel-head {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 11.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-3);
}
/* ── 标题逐行揭示（由进入动画结束时给根元素加的 .entered 触发）──────────────────
   遮罩掀开式：外层 overflow hidden，内层从下方顶上来。
   与"整体淡入"的区别：文字像是**被推出来**的，一行一行，有先后。 */
.stats-page .ttl {
  display: block;
  margin: 6px 0 10px;
}
.stats-page .ttl-line {
  display: block;
  overflow: hidden;
  /* 给下滑的字留出空间，但遮罩只在竖直方向裁切 */
  padding-bottom: 0.06em;
}
.stats-page .ttl-i {
  display: block;
  transform: translateY(105%);
  opacity: 0;
  transition:
    transform 1.05s cubic-bezier(0.22, 1.12, 0.36, 1),
    opacity 0.5s ease;
}
.stats-page.entered .ttl-i {
  transform: none;
  opacity: 1;
}
/* 眉头先到，标题随后 —— 错峰让"出现"有节奏感 */
.stats-page .view-kicker {
  opacity: 0;
  transform: translateY(8px);
  transition:
    opacity 0.6s ease 0.05s,
    transform 0.8s cubic-bezier(0.22, 1.12, 0.36, 1) 0.05s;
}
.stats-page.entered .view-kicker {
  opacity: 1;
  transform: none;
}
.stats-page .view-desc {
  opacity: 0;
  transform: translateY(10px);
  transition:
    opacity 0.7s ease 0.26s,
    transform 0.9s cubic-bezier(0.22, 1.12, 0.36, 1) 0.26s;
}
.stats-page.entered .view-desc {
  opacity: 1;
  transform: none;
}
@media (prefers-reduced-motion: reduce) {
  .stats-page .ttl-i,
  .stats-page .view-kicker,
  .stats-page .view-desc {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
/* ══ 首页整体重构（编辑式版式：编号章节 + 发丝线 + 大留白 + 无浮卡）══════
   学参考稿的做法。参考稿通篇没有阴影与圆角浮卡，层级完全靠"细线 + 留白 +
   字号对比"建立 —— 这是它显得高级的主要原因。这里把原来"一堆圆角浮卡堆叠"
   改为"一份报告"的读法。

   为什么用追加覆盖层而不是改模板：
     · 风险最低（不动结构、不动 JS，随时可撤）
     · 用现有类名精确指定，不会产生"定义了没用"的死样式
   ─────────────────────────────────────────────────────────────────── */

/* ① 页面留白与节奏 */
.stats-page {
  --sec-gap: clamp(56px, 9vh, 128px);
  padding-bottom: clamp(80px, 12vh, 160px);
}

/* ② 英雄区：满屏级呼吸（标题大字 + 超大上下留白） */
.stats-page .view-hero {
  /* 原来 min-height:min(62svh,620px) + align-items:flex-end，
     实测文案从 507px 才开始，上方空了 387px —— 看着像"没加载出来"。
     改为：内容上对齐，高度由内容 + 明确的内边距决定，
     空白因此是"刻意的呼吸"而不是"神秘的虚空"。 */
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: stretch;
  gap: clamp(18px, 2.6vh, 32px);
  padding-top: clamp(36px, 6vh, 78px);
  padding-bottom: clamp(26px, 4vh, 52px);
  border-bottom: 1px solid var(--line);
}
/* 按钮组不再与文案底部对齐，改为跟在文案下方 */
.stats-page .view-hero .header-actions {
  align-self: flex-start;
}
.stats-page .view-hero-copy {
  /* 不再限制 ch 宽度：中文标题在 108px 字号下会被逐字换行。
     改用 max-width 的百分比，保证标题一行放得下，说明文字单独限宽。 */
  max-width: min(100%, 68rem);
}
.stats-page .ttl {
  /* 再放大一档：它是整页的主角 */
  font-size: clamp(2.6rem, 7.6vw, 6.8rem) !important;
  line-height: 0.98 !important;
  letter-spacing: -0.045em !important;
}
.stats-page .view-desc {
  max-width: 40ch;
}

/* ③ 编号章节：每个区标题写成 [NN] — 名称，配上下发丝线 */
.stats-page .panel-head,
.stats-page .fc-head,
.stats-page .rp-head {
  align-items: baseline;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(20px, 3vh, 36px);
}
.stats-page .panel-title,
.stats-page .fc-head .panel-title,
.stats-page .rp-head .panel-title {
  font-size: 11.5px !important;
  letter-spacing: 0.2em !important;
  text-transform: uppercase !important;
  color: var(--ink-2) !important;
}
/* 章节序号：用伪元素加，避免改模板 */
.stats-page .bento > .span2:nth-of-type(1) .panel-head::before {
  content: '[01]';
}
.stats-page .bento > .span2:nth-of-type(2) .panel-head::before {
  content: '[02]';
}
.stats-page .fc-strip .fc-head::before {
  content: '[03]';
}
.stats-page .report-strip .rp-head::before {
  content: '[04]';
}
.stats-page .fc-head::before,
.stats-page .rp-head::before,
.stats-page .panel-head::before {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-right: 2px;
}

/* ④ 去浮卡：圆角归零、阴影去掉、改发丝线。
   注意（踩过的错位 bug）：**网格容器不能设底色**。
   我上一版用 `gap:1px + background:var(--line)` 伪造发丝线，
   结果空出来的格位也被底色填上，看起来是"多出一块没对齐的底"。
   正解：网格只排布，底色与描边交给各自卡片。 */
.stats-page :is(.bento-top, .bento) {
  gap: 14px;
  background: none;
  border: 0;
  margin-top: var(--sec-gap);
}
/* 右列两行**强制等高**：minmax(0,1fr) 会把可用高度均分给两行，
   于是 瓷砖1 + gap + 瓷砖2 恒等于左侧英雄卡的高度，底边自然齐平。
   实测：178.844 × 2 + 14 = 371.688 = 英雄卡高度，几何完全对齐。 */
.stats-page .bento-top {
  grid-template-rows: repeat(2, minmax(0, 1fr));
  align-items: stretch;
}
/* 组版容器框已拆除（用户实测："卡框没有完全覆盖外面的框"）——
   外框 + 内卡两层信号读起来就是错位。现在 .bento-top 只做网格布线，
   每张卡自己是唯一的框，与其余页面的卡片语言一致。 */
.stats-page .bento-top {
  background: none;
  border: 0;
  padding: 0;
}
/*
  卡片 root 一律不画背景/边框/内边距（2026-09-19 二次实测：
  报刊层给的 `background: var(--surface)` + 上下 clamp(18-32px) padding
  让圆角玻璃卡浮在一块更大的方形底上 —— 浅色下与纸色同形看不出来，
  深色下原形毕露，就是用户截图里的"槽中卡"）。
  可见卡片只有 .gcard-body（玻璃 + 渐变描边），它 height:100% 铺满格位。
  留白全部交给 .gcard-body 自身的 padding（24px 26px），不再双层叠加。
*/
.stats-page .bento-top > *,
.stats-page :is(.b-hero, .b-tile, .span2, .span3) {
  background: transparent !important;
  border: 0 !important;
  padding: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
.stats-page .bento-top > * {
  height: 100%;
}
.stats-page .b-tile {
  display: flex;
  flex-direction: column;
  justify-content: center;
}
/* 章节之间拉开发丝线 */
.stats-page :is(.fc-strip, .report-strip) {
  margin-top: var(--sec-gap) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  border: 1px solid var(--line) !important;
  background: var(--surface) !important;
}

/* ⑤ 数字与标签排版：读数更大、标签统一极小大写等宽 */
.stats-page :is(.b-tile .num, .m-num, .rp-cluster b) {
  font-size: clamp(1.7rem, 2.9vw, 2.6rem) !important;
  line-height: 1 !important;
  letter-spacing: -0.03em !important;
}
.stats-page :is(.m-label, .b-tile .k, .cap, .rp-hint) {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ink-3);
}
.stats-page .cap {
  text-transform: none;
}

/* ⑥ 内容内边距统一（原来各卡不同，读起来散） */
.stats-page :is(.b-hero, .b-tile, .span2, .span3) > * {
  padding-left: clamp(18px, 2.2vw, 32px);
  padding-right: clamp(18px, 2.2vw, 32px);
}
.stats-page :is(.b-hero, .b-tile, .span2, .span3) {
  padding-top: clamp(18px, 2.2vw, 32px);
  padding-bottom: clamp(18px, 2.2vw, 32px);
}

/* ⑦ 章节入场：错峰（由 .entered 触发）+ 过冲曲线。只动 transform/opacity */
.stats-page .bento-top,
.stats-page .bento,
.stats-page .fc-strip,
.stats-page .report-strip {
  opacity: 0;
  transform: translateY(20px);
  transition:
    opacity 0.7s var(--ease),
    transform 0.9s cubic-bezier(0.22, 1.12, 0.36, 1);
}
.stats-page.entered .bento-top {
  opacity: 1;
  transform: none;
  transition-delay: 0.12s;
}
.stats-page.entered .bento {
  opacity: 1;
  transform: none;
  transition-delay: 0.2s;
}
.stats-page.entered .fc-strip {
  opacity: 1;
  transform: none;
  transition-delay: 0.28s;
}
.stats-page.entered .report-strip {
  opacity: 1;
  transform: none;
  transition-delay: 0.36s;
}

@media (prefers-reduced-motion: reduce) {
  .stats-page .bento-top,
  .stats-page .bento,
  .stats-page .fc-strip,
  .stats-page .report-strip {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>
