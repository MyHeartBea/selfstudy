<script setup>
/** 学习统计 · 墨韵 2.0 Bento：英雄卡 + 瓷砖 + SVG 趋势 + 热力图 + 薄弱点直通 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { sourceTypeColor, subjectColor } from '../composables/useBaseData'
import { useCountUp } from '../utils/useCountUp'
import { reveal } from '../directives/reveal'
import ReviewHeatmap from '../components/ReviewHeatmap.vue'
import Icon from '../ui/Icon.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiProgress from '../ui/UiProgress.vue'
import UiButton from '../ui/UiButton.vue'
import GlassCard from '../ui/GlassCard.vue'
import MetricTile from '../ui/MetricTile.vue'
import RingProgress from '../ui/RingProgress.vue'
import AreaChart from '../ui/AreaChart.vue'
import BarRow from '../ui/BarRow.vue'

const loading = ref(false)
const router = useRouter()
const stats = ref({
  total_mistakes: 0,
  today_new: 0,
  by_subject: [],
  by_sub_subject: [],
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

// —— 今日速览（保留全部 8 指标）——
const todayMini = computed(() => [
  { key: 'done', label: '今日已复习', value: nReviewed.value, unit: `/ ${reviewStats.value.due_today}`, icon: 'check', tone: 'green' },
  { key: 'acc', label: '今日正确率', value: nAccToday.value, unit: '%', icon: 'target', tone: 'accent' },
  { key: 'mastery', label: '平均掌握度', value: nMastery.value, unit: '', icon: 'sparkles', tone: 'violet' },
  { key: 'streak', label: '连续复习', value: nStreak.value, unit: ' 天', icon: 'flame', tone: 'gold' },
])

// —— 7 天趋势（SVG 面积图） ——
const dayList = computed(() => reviewStats.value.last_7_days || [])
const trendLabels = computed(() => dayList.value.map((d) => d.day.slice(5)))
const trendSeries = computed(() => [
  { name: '完成次数', color: 'var(--accent)', values: dayList.value.map((d) => d.count) },
])

// —— 掌握度分布（条形） ——
const masteryRows = computed(() => {
  const list = reviewStats.value.mastery_distribution || []
  const max = Math.max(1, ...list.map((i) => i.count))
  return list.map((item) => ({
    label: item.mastery === 0 ? '新题' : `${item.mastery} 级`,
    count: item.count,
    percent: Math.round((item.count / max) * 100),
  }))
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
  // max 为该列表预计算的最大值（见 subjectMax 等 computed）
  return Math.round((count / Math.max(1, max)) * 100)
}

// 各分布列表的最大值只算一次
const subjectMax = computed(() => Math.max(1, ...stats.value.by_subject.map((s) => s.count)))
const subSubjectMax = computed(() => Math.max(1, ...stats.value.by_sub_subject.map((s) => s.count)))
const sourceMax = computed(() => Math.max(1, ...(stats.value.by_source_type || []).map((s) => s.count)))
const weakMax = computed(() => Math.max(1, ...(reviewStats.value.weakest_tags || []).map((w) => w.wrong_count)))

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

    <!-- Bento 主网格 -->
    <div class="bento">
      <!-- 英雄卡：今日待复习 -->
      <GlassCard class="b-hero" :hover="false">
        <span class="hero-seal" aria-hidden="true">今</span>
        <div class="hero-bg" aria-hidden="true"></div>
        <div class="hero-label"><Icon name="clock" :size="15" /> 今日待复习</div>
        <div class="hero-body">
          <div class="hero-left">
            <div class="hero-value num">{{ nDue }}</div>
            <div class="hero-delta">今日新增 <b>{{ nTodayNew }}</b> 题 · 新错题优先</div>
            <UiButton variant="primary" @click="router.push('/review')">
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

      <!-- 瓷砖 -->
      <GlassCard class="b-tile">
        <MetricTile icon="layers" :value="nTotal" label="累计错题" tone="accent" />
      </GlassCard>
      <GlassCard class="b-tile">
        <MetricTile icon="chart" :value="nTotalAcc" unit="%" label="累计正确率 · 总复习" tone="teal" />
      </GlassCard>

      <!-- 今日速览（4 指标细条） -->
      <GlassCard class="b-strip span3" :hover="false" :pad="false">
        <div class="strip-inner">
          <div v-for="m in todayMini" :key="m.key" class="strip-item">
            <span class="strip-icon" :class="`tone-${m.tone}`"><Icon :name="m.icon" :size="16" /></span>
            <b class="num">{{ m.value }}</b><i v-if="m.unit" class="num">{{ m.unit }}</i>
            <span class="strip-label">{{ m.label }}</span>
          </div>
        </div>
      </GlassCard>

      <!-- 趋势 + 掌握度 -->
      <GlassCard class="span2">
        <div class="panel-head">
          <h3 class="panel-title">复习趋势</h3>
          <span class="cap">近 7 天完成次数（描边生长）</span>
        </div>
        <AreaChart v-if="dayList.length" :labels="trendLabels" :series="trendSeries" :height="200" />
        <UiEmpty v-else text="近 7 天暂无复习记录" icon="chart" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title">掌握度分布</h3>
        <p class="cap">{{ stats.total_mistakes }} 道错题 · 0-5 级</p>
        <div v-if="masteryRows.length" class="mastery-bars">
          <BarRow
            v-for="row in masteryRows"
            :key="row.label"
            :label="row.label"
            :percentage="row.percent"
            :value="row.count"
          />
        </div>
        <UiEmpty v-else text="暂无掌握度数据" icon="layers" />
      </GlassCard>

      <!-- 热力图 + 薄弱点 -->
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
        <p class="cap">按累计答错排序</p>
        <div v-if="reviewStats.weakest_tags.length" class="weak-list">
          <button
            v-for="(row, i) in reviewStats.weakest_tags.slice(0, 5)"
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
            <span class="w-bar"><BarRow :percentage="percentOf(row.wrong_count, weakMax)" :bar-height="6" /></span>
          </button>
        </div>
        <UiEmpty v-else text="暂无薄弱知识点" icon="target" />
        <UiButton v-if="reviewStats.weakest_tags.length" variant="outline" block size="sm" class="weak-more" @click="practiceTag(reviewStats.weakest_tags[0].tag_name)">
          直通薄弱练习
        </UiButton>
      </GlassCard>
    </div>

    <!-- 分布与明细 -->
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
          <div v-for="s in stats.by_source_type" :key="s.source_type" class="bar-row">
            <div class="bar-name">{{ s.name }}</div>
            <UiProgress :percentage="percentOf(s.count, sourceMax)" :color="sourceTypeColor(s.source_type)" />
            <div class="bar-nums">{{ s.count }} 题</div>
          </div>
        </div>
        <UiEmpty v-else text="暂无题目来源数据" icon="tag" />
      </GlassCard>
    </div>

    <GlassCard class="block-card">
      <h3 class="panel-title">各科目统计</h3>
      <div v-for="s in stats.by_subject" :key="s.subject_id" class="bar-row">
        <div class="bar-name">{{ s.name }}</div>
        <UiProgress :percentage="percentOf(s.count, subjectMax)" :color="subjectColor(s.subject_id)" />
        <div class="bar-nums">
          {{ s.count }} 题 <span class="avg">均难 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
      <UiEmpty v-if="!stats.by_subject.length" text="暂无科目数据" icon="book" />
    </GlassCard>

    <div class="grid-2">
      <GlassCard>
        <h3 class="panel-title">薄弱知识点</h3>
        <table v-if="reviewStats.weakest_tags.length" class="plain-table">
          <thead>
            <tr>
              <th>知识点</th>
              <th class="num">累计答错</th>
              <th class="num">关联错题</th>
              <th class="op"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in reviewStats.weakest_tags" :key="row.tag_name">
              <td class="tag-cell">{{ row.tag_name }}</td>
              <td class="num">{{ row.wrong_count }}</td>
              <td class="num">{{ row.mistake_count }}</td>
              <td class="op">
                <UiButton size="sm" variant="outline" @click="practiceTag(row.tag_name)">练这组题</UiButton>
              </td>
            </tr>
          </tbody>
        </table>
        <UiEmpty v-else text="暂无薄弱知识点" icon="target" />
      </GlassCard>

      <GlassCard>
        <h3 class="panel-title">各科目复习情况</h3>
        <table v-if="reviewStats.by_subject && reviewStats.by_subject.length" class="plain-table">
          <thead>
            <tr>
              <th>科目</th>
              <th class="num">错题数</th>
              <th class="num">复习次数</th>
              <th class="num">正确率</th>
              <th class="num">累计答错</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in reviewStats.by_subject" :key="row.name">
              <td class="tag-cell">{{ row.name }}</td>
              <td class="num">{{ row.mistake_count }}</td>
              <td class="num">{{ row.review_count }}</td>
              <td class="num acc">{{ row.accuracy }}%</td>
              <td class="num">{{ row.wrong_count }}</td>
            </tr>
          </tbody>
        </table>
        <UiEmpty v-else text="暂无复习数据" icon="refresh" />
      </GlassCard>
    </div>

    <GlassCard v-if="stats.by_sub_subject && stats.by_sub_subject.length" class="block-card">
      <h3 class="panel-title">各二级科目统计</h3>
      <div v-for="s in stats.by_sub_subject" :key="s.sub_subject_id" class="bar-row">
        <div class="bar-name">{{ s.subject_name }} · {{ s.name }}</div>
        <UiProgress :percentage="percentOf(s.count, subSubjectMax)" :color="subjectColor(s.subject_id)" />
        <div class="bar-nums">
          {{ s.count }} 题 <span class="avg">均难 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
    </GlassCard>
  </div>
</template>

<style scoped>
/* ---------- Bento ---------- */
.bento {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.span2 { grid-column: span 2; }
.span3 { grid-column: span 3; }

.b-hero { grid-column: span 2; grid-row: span 2; display: flex; flex-direction: column; }
.b-tile { display: flex; align-items: center; }

/* 英雄卡 */
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
.hero-value {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 72px;
  line-height: 1.05;
  color: var(--accent);
  letter-spacing: -0.02em;
  text-shadow: 0 2px 24px color-mix(in srgb, var(--accent) 22%, transparent);
}
.hero-delta { font-size: 13px; color: var(--ink-3); margin: 6px 0 20px; }
.hero-delta b { color: var(--green); font-weight: 700; }
.ring-center-text b { display: block; font-family: var(--font-display); font-size: 26px; font-weight: 900; line-height: 1.1; }
.ring-center-text span { display: block; font-size: 11.5px; color: var(--ink-3); margin-top: 2px; }

/* 今日速览细条 */
.strip-inner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  padding: 14px 20px;
}
.strip-item {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  padding: 2px 8px;
}
.strip-item + .strip-item { border-left: 1px solid var(--line); }
.strip-icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  flex: none;
  display: grid;
  place-items: center;
}
.strip-item b { font-family: var(--font-display); font-size: 21px; font-weight: 900; }
.strip-item i { font-style: normal; font-size: 12px; color: var(--ink-3); }
.strip-label { font-size: 12px; color: var(--ink-3); margin-left: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tone-accent { background: var(--accent-soft); color: var(--accent); }
.tone-teal { background: var(--teal-soft); color: var(--teal); }
.tone-gold { background: var(--gold-soft); color: var(--gold); }
.tone-green { background: var(--green-soft); color: var(--green); }
.tone-violet { background: var(--violet-soft); color: var(--violet); }

/* 面板通用 */
.panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.panel-title {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  margin-bottom: 4px;
}
.cap { font-size: 12.5px; color: var(--ink-3); }

.mastery-bars { display: flex; flex-direction: column; gap: 13px; margin-top: 12px; }

/* 薄弱点列表 */
.weak-list { display: flex; flex-direction: column; gap: 4px; margin-top: 10px; }
.weak-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 9px 10px;
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
.weak-more { margin-top: 12px; }

/* 下部布局 */
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.block-card { margin-bottom: 16px; }

/* 环形图 */
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

/* 条形行 */
.bar-row {
  display: grid;
  grid-template-columns: 150px 1fr 110px;
  align-items: center;
  gap: 12px;
  padding: 7px 0;
}
.bar-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-nums { font-size: 12px; color: var(--ink-3); text-align: right; white-space: nowrap; }
.bar-nums .avg { margin-left: 6px; }

/* 表格 */
.plain-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.plain-table th {
  text-align: left;
  font-size: 11.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--ink-3);
  padding: 6px 8px;
  border-bottom: 1px solid var(--line);
}
.plain-table td {
  padding: 9px 8px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-2);
}
.plain-table tr:last-child td { border-bottom: none; }
.plain-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.plain-table th.num { text-align: right; }
.plain-table .acc { color: var(--green); font-weight: 700; }
.plain-table .tag-cell { color: var(--ink); font-weight: 600; }
.plain-table .op { text-align: right; width: 90px; }

@media (max-width: 1100px) {
  .bento { grid-template-columns: repeat(2, 1fr); }
  .b-hero { grid-column: span 2; }
  .strip-inner { grid-template-columns: repeat(2, 1fr); gap: 10px 0; }
  .strip-item:nth-child(3) { border-left: none; }
}
@media (max-width: 860px) {
  .bento { grid-template-columns: 1fr; }
  .span2, .span3, .b-hero { grid-column: span 1; }
  .b-hero .hero-body { flex-direction: column; align-items: flex-start; }
  .hero-value { font-size: 56px; }
  .grid-2 { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 100px 1fr 90px; }
  .strip-inner { grid-template-columns: 1fr 1fr; }
}
</style>
