<script setup>
/** 学习统计 · 墨韵 2.0 Bento：英雄卡 + 瓷砖 + SVG 趋势 + 墨阶掌握度 + 热力图 + 科目分析 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { sourceTypeColor, subjectColor } from '../composables/useBaseData'
import { useCountUp } from '../utils/useCountUp'
import { reveal } from '../directives/reveal'
import ReviewHeatmap from '../components/ReviewHeatmap.vue'
import Icon from '../ui/Icon.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiButton from '../ui/UiButton.vue'
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
const nMastery = useCountUp(computed(() => reviewStats.value.avg_mastery), {
  format: (v) => (Math.round(v * 10) / 10).toFixed(1),
})
const nTotalAcc = useCountUp(computed(() => reviewStats.value.total_accuracy))
const nStreak = useCountUp(computed(() => reviewStats.value.streak_days))

const ringPercent = computed(() => {
  const due = Number(reviewStats.value.due_today) || 0
  return due ? Math.min(100, Math.round(((Number(reviewStats.value.reviewed_today) || 0) / due) * 100)) : 0
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
    (reviewStats.value.mastery_distribution || []).map((i) => [Number(i.mastery), Number(i.count) || 0]),
  )
  const depths = [14, 26, 42, 58, 76]
  const rows = [0, 1, 2, 3, 4, 5].map((level) => ({
    level,
    label: level === 0 ? '新题' : `${level} 级`,
    count: map.get(level) || 0,
    color: level === 5 ? 'var(--accent)' : `color-mix(in srgb, var(--ink) ${depths[level - 1] || 14}%, var(--surface-2))`,
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

const sourceMax = computed(() => Math.max(1, ...(stats.value.by_source_type || []).map((s) => s.count)))
const subjectMax = computed(() => Math.max(1, ...stats.value.by_subject.map((s) => s.count)))
const weakMax = computed(() => Math.max(1, ...(reviewStats.value.weakest_tags || []).map((w) => w.wrong_count)))

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
    const row = map.get(r.name) || { name: r.name, subject_id: null, count: Number(r.mistake_count) || 0, avg_difficulty: 0 }
    row.review_count = Number(r.review_count) || 0
    row.accuracy = Number(r.accuracy) || 0
    row.wrong_count = Number(r.wrong_count) || 0
    map.set(r.name, row)
  }
  return [...map.values()]
})

async function loadStats() {
  loading.value = true
  try {
    // 优先走聚合接口，回退到两个独立接口
    const res = await request.get('/dashboard', { silent: true })
    stats.value = res.data.data.stats
    reviewStats.value = res.data.data.reviews
  } catch (err) {
    try {
      const [res, reviewRes] = await Promise.all([
        request.get('/stats'),
        request.get('/reviews/stats'),
      ])
      stats.value = res.data.data
      reviewStats.value = reviewRes.data.data
    } catch (err2) {
      // 错误提示由请求拦截器统一处理
    }
  } finally {
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

onMounted(loadStats)
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Learning Analytics</div>
        <h2>学习统计</h2>
        <p class="view-desc">用数据看复习节奏，找到下一轮该攻克的薄弱点。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="primary" @click="router.push('/review')">
          <Icon name="refresh" :size="15" />
          开始今日复习
        </UiButton>
      </div>
    </div>

    <!-- 顶部区：英雄卡 + 两张瓷砖（子网格两行强制等高，卡片对齐） -->
    <div class="bento-top">
      <GlassCard class="b-hero" :hover="false" @mousemove="onHeroMove" @mouseleave="onHeroLeave">
        <span class="hero-seal" aria-hidden="true">今</span>
        <div class="hero-bg" aria-hidden="true"></div>
        <span v-if="reviewStats.streak_days" class="streak-chip" :title="`最长连续纪录见「连续复习」`">
          <Icon name="flame" :size="14" />
          连续 <b class="num">{{ nStreak }}</b> 天
        </span>
        <div class="hero-label"><Icon name="clock" :size="15" /> 今日待复习</div>
        <div class="hero-body">
          <div class="hero-left">
            <div class="hero-value num">{{ nDue }}</div>
            <div class="hero-delta">今日新增 <b>{{ nTodayNew }}</b> 题 · 新错题优先</div>
            <div class="hero-chips">
              <span class="h-chip"><Icon name="target" :size="13" />今日正确率 <b class="num">{{ nAccToday }}<i>%</i></b></span>
              <span class="h-chip"><Icon name="sparkles" :size="13" />平均掌握度 <b class="num">{{ nMastery }}</b></span>
            </div>
            <UiButton variant="primary" class="hero-cta" @click="router.push('/review')">
              开始今日复习
              <Icon name="chevron-right" :size="15" />
            </UiButton>
          </div>
          <RingProgress :percentage="ringPercent">
            <div class="ring-center-text">
              <b class="num">{{ nReviewed }}/{{ reviewStats.due_today }}</b>
              <span>今日已完成</span>
            </div>
          </RingProgress>
        </div>
      </GlassCard>

      <GlassCard class="b-tile">
        <MetricTile icon="layers" :value="nTotal" label="累计错题" tone="accent" />
      </GlassCard>
      <GlassCard class="b-tile">
        <MetricTile icon="chart" :value="nTotalAcc" unit="%" label="累计正确率 · 总复习" tone="teal" />
      </GlassCard>
    </div>

    <!-- 主 Bento：趋势 + 墨阶 / 热力图 + 薄弱点 -->
    <div class="bento">
      <GlassCard class="span2">
        <div class="panel-head">
          <h3 class="panel-title">复习趋势</h3>
          <span class="cap">近 7 天完成次数（描边生长）</span>
        </div>
        <AreaChart v-if="dayList.length" :labels="trendLabels" :series="trendSeries" :height="200" />
        <UiEmpty v-else text="近 7 天暂无复习记录" icon="chart" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title">掌握度墨阶</h3>
        <p class="cap">{{ stats.total_mistakes }} 道错题 · 墨色越深掌握越牢</p>
        <div class="m-steps">
          <div v-for="s in masterySteps" :key="s.level" class="m-step" :style="{ '--d': s.delay + 'ms' }">
            <b class="num">{{ s.count }}</b>
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

      <GlassCard class="span2">
        <div class="panel-head">
          <h3 class="panel-title">复习热力图</h3>
          <UiButton size="sm" variant="ghost" @click="router.push('/review')">
            去复习，点亮今天
          </UiButton>
        </div>
        <ReviewHeatmap :days="119" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title">薄弱知识点</h3>
        <p class="cap">按累计答错排序 · 点击直通练习</p>
        <div v-if="reviewStats.weakest_tags.length" class="weak-list">
          <button
            v-for="(row, i) in reviewStats.weakest_tags"
            :key="row.tag_name"
            type="button"
            class="weak-item"
            @click="practiceTag(row.tag_name)"
          >
            <span class="w-rank num">{{ i + 1 }}</span>
            <span class="w-name">
              <b>{{ row.tag_name }}</b>
              <span>错 {{ row.wrong_count }} 次 · 关联 {{ row.mistake_count }} 题</span>
            </span>
            <span class="w-bar"><span class="w-track"><i :style="{ width: percentOf(row.wrong_count, weakMax) + '%' }"></i></span></span>
          </button>
        </div>
        <UiEmpty v-else text="暂无薄弱知识点" icon="target" />
        <UiButton v-if="reviewStats.weakest_tags.length" variant="outline" block size="sm" class="weak-more" @click="practiceTag(reviewStats.weakest_tags[0].tag_name)">
          直通薄弱练习
        </UiButton>
      </GlassCard>
    </div>

    <!-- 分布 -->
    <div class="grid-2">
      <GlassCard>
        <h3 class="panel-title">题型分布</h3>
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
            <div class="donut-total num">{{ typeDonut.total }}</div>
            <div class="donut-total-label">总题数</div>
          </div>
          <div class="donut-legend">
            <div v-for="seg in typeDonut.segs" :key="seg.name" class="legend-item">
              <span class="legend-dot" :style="{ background: seg.color }"></span>
              <span class="legend-name">{{ seg.name }}</span>
              <span class="legend-num num">{{ seg.count }}</span>
              <span class="legend-pct num">{{ seg.percent }}%</span>
            </div>
          </div>
        </div>
        <UiEmpty v-else text="暂无题型数据" icon="list" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title">题目来源分布</h3>
        <div v-if="stats.by_source_type && stats.by_source_type.length">
          <div v-for="s in stats.by_source_type" :key="s.source_type" class="src-row">
            <span class="s-name">{{ s.name }}</span>
            <span class="src-track"><i :style="{ width: percentOf(s.count, sourceMax) + '%', background: sourceTypeColor(s.source_type) }"></i></span>
            <span class="s-nums num">{{ s.count }} 题</span>
          </div>
        </div>
        <UiEmpty v-else text="暂无题目来源数据" icon="tag" />
      </GlassCard>
    </div>

    <!-- 科目分析：规模 × 效果 合并一张图 -->
    <GlassCard class="block-card">
      <div class="panel-head">
        <h3 class="panel-title">科目分析</h3>
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
          <span class="s-nums num">
            <b>{{ s.count }}</b> 题
            <em>复习 {{ s.review_count || 0 }}</em>
            <em :class="{ good: (s.accuracy || 0) >= 70, warn: (s.accuracy || 0) < 50 }">{{ s.accuracy || 0 }}%</em>
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
/* ---------- 顶部区（子网格：两行强制等高 → 卡片对齐） ---------- */
.bento-top {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  grid-template-rows: repeat(2, minmax(158px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.b-tile { display: flex; }
.b-tile :deep(.gcard-body) { flex: 1; display: flex; align-items: center; }

/* ---------- 主 Bento ---------- */
.bento {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.span2 { grid-column: span 2; }

/* 英雄卡 */
.b-hero { grid-row: 1 / 3; display: flex; flex-direction: column; transition: transform 0.3s var(--ease); }
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
  background:
    radial-gradient(420px 260px at 8% 0%, var(--accent-soft), transparent 70%),
    radial-gradient(380px 240px at 100% 100%, var(--teal-soft), transparent 70%);
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
.streak-chip svg { animation: flame-flicker 2.2s ease-in-out infinite; }
@keyframes flame-flicker {
  0%, 100% { transform: scale(1) rotate(0deg); }
  30% { transform: scale(1.14) rotate(-4deg); }
  60% { transform: scale(1.06) rotate(3deg); }
}
.hero-label {
  position: relative;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13.5px;
  color: var(--ink-2);
}
.hero-label :deep(svg) { color: var(--accent); }
.hero-body {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 10px;
}
.hero-left { min-width: 0; }
.hero-value {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 72px;
  line-height: 1.05;
  color: var(--accent);
  letter-spacing: -0.02em;
  text-shadow: 0 2px 24px color-mix(in srgb, var(--accent) 22%, transparent);
}
.hero-delta { font-size: 13px; color: var(--ink-3); margin: 6px 0 14px; }
.hero-delta b { color: var(--green); font-weight: 700; }
.hero-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
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
.h-chip svg { color: var(--accent); }
.h-chip b { color: var(--ink); font-weight: 800; }
.h-chip i { font-style: normal; font-size: 11px; color: var(--ink-3); }
.ring-center-text b { display: block; font-family: var(--font-display); font-size: 26px; font-weight: 900; line-height: 1.1; }
.ring-center-text span { display: block; font-size: 11.5px; color: var(--ink-3); margin-top: 2px; }

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
.m-step > b { font-family: var(--font-display); font-weight: 900; font-size: 16px; }
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
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}
.m-label { font-size: 11.5px; color: var(--ink-3); white-space: nowrap; }

/* ---------- 面板通用 ---------- */
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.panel-title {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  margin-bottom: 4px;
}
.cap { font-size: 12.5px; color: var(--ink-3); }

/* ---------- 薄弱点列表 ---------- */
.weak-list { display: flex; flex-direction: column; gap: 2px; margin-top: 10px; }
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
  transition: background 0.18s var(--ease), transform 0.18s var(--ease);
}
.weak-item:hover { background: var(--accent-soft); transform: translateX(4px); }
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
.weak-item:hover .w-rank { transform: rotate(-8deg) scale(1.12); background: var(--accent-soft); color: var(--accent); }
.w-name { flex: 1; min-width: 0; }
.w-name b {
  font-size: 13.5px;
  font-weight: 600;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--ink);
}
.w-name span { font-size: 11.5px; color: var(--ink-3); }
.w-bar { width: 64px; flex: none; }
.w-track { display: block; height: 6px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
.w-track i { display: block; height: 100%; border-radius: 99px; background: var(--accent); transition: width 1.1s var(--spring); }
.weak-more { margin-top: 12px; }

/* ---------- 下部布局 ---------- */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.block-card { margin-bottom: 16px; }

/* ---------- 环形图 ---------- */
.donut-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 22px;
}
.donut { width: 148px; height: 148px; flex: none; }
.donut-track { fill: none; stroke: var(--surface-2); stroke-width: 6; }
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
.donut-total { font-family: var(--font-display); font-size: 30px; font-weight: 800; line-height: 1; }
.donut-total-label { font-size: 10.5px; color: var(--ink-3); margin-top: 3px; letter-spacing: 0.08em; }
.donut-legend { flex: 1; display: flex; flex-direction: column; gap: 9px; min-width: 0; }
.legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.legend-dot { width: 9px; height: 9px; border-radius: 3px; flex: none; }
.legend-name { color: var(--ink-2); }
.legend-num { margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }
.legend-pct { color: var(--ink-3); font-size: 12px; width: 38px; text-align: right; }

/* ---------- 来源 / 科目条形行 ---------- */
.src-row,
.subj-row {
  display: grid;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}
.src-row { grid-template-columns: 150px 1fr 64px; }
.subj-row {
  grid-template-columns: 150px 1fr minmax(300px, auto);
  transition: background 0.16s var(--ease);
  border-radius: 10px;
  padding-left: 8px;
  padding-right: 8px;
}
.subj-row:hover { background: var(--accent-soft); }
.s-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.src-track { display: block; height: 9px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
.src-track i { display: block; height: 100%; border-radius: 99px; transition: width 1.1s var(--spring); }
.s-bar { display: block; height: 12px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
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
.subj-row .s-nums em { font-style: normal; margin-left: 12px; }
.subj-row .s-nums b { font-family: var(--font-display); font-size: 15px; color: var(--ink); }
.subj-row .s-nums .good { color: var(--green); font-weight: 700; }
.subj-row .s-nums .warn { color: var(--red); font-weight: 700; }

@media (max-width: 1100px) {
  .bento { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 860px) {
  .bento { grid-template-columns: 1fr; }
  .span2 { grid-column: span 1; }
  .bento-top { grid-template-columns: 1fr; grid-template-rows: auto auto auto; }
  .b-hero { grid-row: auto; }
  .b-hero .hero-body { flex-direction: column; align-items: flex-start; }
  .hero-value { font-size: 56px; }
  .grid-2 { grid-template-columns: 1fr; }
  .subj-row { grid-template-columns: 96px 1fr; }
  .subj-row .s-nums { grid-column: 1 / 3; text-align: left; }
  .subj-row .s-nums em:first-child { margin-left: 0; }
}
</style>
