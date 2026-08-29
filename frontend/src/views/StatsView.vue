<script setup>
/** 学习统计仪表盘：聚合接口 + 数字滚动 + SVG 环形图 + 生长柱状图 */
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

const metricCards = computed(() => [
  { key: 'total', label: '总错题数', value: nTotal.value, icon: 'layers', color: 'var(--accent)' },
  { key: 'today', label: '今日新增', value: nTodayNew.value, icon: 'plus-circle', color: 'var(--blue)' },
  { key: 'due', label: '今日待复习', value: nDue.value, icon: 'clock', color: 'var(--gold)' },
  { key: 'done', label: '今日已复习', value: nReviewed.value, icon: 'check', color: 'var(--green)' },
  { key: 'acc', label: '今日正确率', value: nAccToday.value + '%', icon: 'target', color: 'var(--red)' },
  { key: 'mastery', label: '平均掌握度', value: nMastery.value, icon: 'sparkles', color: 'var(--violet)' },
  { key: 'totalacc', label: '累计正确率', value: nTotalAcc.value + '%', icon: 'chart', color: 'var(--teal)' },
  { key: 'streak', label: '连续复习', value: nStreak.value + ' 天', icon: 'flame', color: 'var(--gold)' },
])

// —— 7 天趋势（柱状生长，加载后触发） ——
const dayList = computed(() => reviewStats.value.last_7_days || [])
const maxDayCount = computed(() =>
  Math.max(1, ...dayList.value.map((item) => item.count)),
)
const barsGrown = ref(false)
function barHeight(count) {
  const full = Math.max(4, Math.round((count / maxDayCount.value) * 120))
  return barsGrown.value ? full : 0
}

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

function percentOf(count, items) {
  const max = Math.max(1, ...(items || []).map((item) => item.count))
  return Math.round((count / max) * 100)
}

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
      barsGrown.value = true
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

    <div class="stats-cards">
      <div
        v-for="(card, i) in metricCards"
        :key="card.key"
        v-reveal="i * 45"
        class="stat-card card"
      >
        <span class="stat-icon" :style="{ background: `color-mix(in srgb, ${card.color} 12%, transparent)`, color: card.color }">
          <Icon :name="card.icon" :size="19" />
        </span>
        <div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </div>
    </div>

    <section v-reveal class="card card-pad heat-card">
      <div class="heat-head">
        <h3 class="panel-title">复习热力图</h3>
        <UiButton size="sm" variant="ghost" @click="router.push('/review')">
          去复习，点亮今天
        </UiButton>
      </div>
      <ReviewHeatmap :days="119" />
    </section>

    <div class="grid-2">
      <section v-reveal class="card card-pad">
        <h3 class="panel-title">近 7 天复习趋势</h3>
        <div v-if="dayList.length" class="day-bars">
          <div v-for="d in dayList" :key="d.day" class="day-bar-item">
            <span class="day-count">{{ d.count }}</span>
            <div class="day-bar" :style="{ height: barHeight(d.count) + 'px' }"></div>
            <span class="day-label">{{ d.day.slice(5) }}</span>
          </div>
        </div>
        <UiEmpty v-else text="近 7 天暂无复习记录" icon="chart" />
      </section>

      <section v-reveal="60" class="card card-pad">
        <h3 class="panel-title">掌握度分布</h3>
        <div v-if="reviewStats.mastery_distribution.length" class="mastery-grid">
          <div
            v-for="(item, i) in reviewStats.mastery_distribution"
            :key="item.mastery"
            v-reveal="i * 40"
            class="mastery-item"
          >
            <div class="mastery-count">{{ item.count }}</div>
            <div class="mastery-level">{{ item.mastery === 0 ? '新题' : `${item.mastery} 级` }}</div>
          </div>
        </div>
        <UiEmpty v-else text="暂无掌握度数据" icon="layers" />
      </section>
    </div>

    <div class="grid-2">
      <section v-reveal class="card card-pad donut-card">
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
            <div class="donut-total">{{ typeDonut.total }}</div>
            <div class="donut-total-label">总题数</div>
          </div>
          <div class="donut-legend">
            <div v-for="seg in typeDonut.segs" :key="seg.name" class="legend-item">
              <span class="legend-dot" :style="{ background: seg.color }"></span>
              <span class="legend-name">{{ seg.name }}</span>
              <span class="legend-num">{{ seg.count }}</span>
              <span class="legend-pct">{{ seg.percent }}%</span>
            </div>
          </div>
        </div>
        <UiEmpty v-else text="暂无题型数据" icon="list" />
      </section>

      <section v-reveal="60" class="card card-pad">
        <h3 class="panel-title">题目来源分布</h3>
        <div v-if="stats.by_source_type && stats.by_source_type.length">
          <div v-for="s in stats.by_source_type" :key="s.source_type" class="bar-row">
            <div class="bar-name">{{ s.name }}</div>
            <UiProgress :percentage="percentOf(s.count, stats.by_source_type)" :color="sourceTypeColor(s.source_type)" />
            <div class="bar-nums">{{ s.count }} 题</div>
          </div>
        </div>
        <UiEmpty v-else text="暂无题目来源数据" icon="tag" />
      </section>
    </div>

    <section v-reveal class="card card-pad">
      <h3 class="panel-title">各科目统计</h3>
      <div v-for="s in stats.by_subject" :key="s.subject_id" class="bar-row">
        <div class="bar-name">{{ s.name }}</div>
        <UiProgress :percentage="percentOf(s.count, stats.by_subject)" :color="subjectColor(s.subject_id)" />
        <div class="bar-nums">
          {{ s.count }} 题 <span class="avg">均难 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
    </section>

    <div class="grid-2">
      <section v-reveal class="card card-pad">
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
      </section>

      <section v-reveal="60" class="card card-pad">
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
      </section>
    </div>

    <section v-if="stats.by_sub_subject && stats.by_sub_subject.length" v-reveal class="card card-pad">
      <h3 class="panel-title">各二级科目统计</h3>
      <div v-for="s in stats.by_sub_subject" :key="s.sub_subject_id" class="bar-row">
        <div class="bar-name">{{ s.subject_name }} · {{ s.name }}</div>
        <UiProgress :percentage="percentOf(s.count, stats.by_sub_subject)" :color="subjectColor(s.subject_id)" />
        <div class="bar-nums">
          {{ s.count }} 题 <span class="avg">均难 {{ Number(s.avg_difficulty).toFixed(1) }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}
@media (max-width: 980px) { .stats-cards { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 520px) { .stats-cards { grid-template-columns: 1fr; } }

.stat-card {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 16px;
  transition: transform 0.25s cubic-bezier(0.22, 0.8, 0.36, 1), box-shadow 0.25s, border-color 0.25s;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-2);
  border-color: color-mix(in srgb, var(--accent) 30%, var(--line));
}
.stat-icon {
  width: 42px;
  height: 42px;
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
}
.stat-value {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.stat-label { font-size: 12px; color: var(--ink-3); margin-top: 2px; }

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
@media (max-width: 860px) { .grid-2 { grid-template-columns: 1fr; } }

.panel-title {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  margin-bottom: 16px;
}

.heat-card { margin-bottom: 14px; }
.heat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.heat-head .panel-title { margin-bottom: 12px; }

.day-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  min-height: 160px;
  padding: 0 6px;
}
.day-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.day-bar {
  width: 100%;
  max-width: 44px;
  border-radius: 7px 7px 3px 3px;
  background: linear-gradient(180deg, var(--accent) 0%, color-mix(in srgb, var(--accent) 55%, transparent) 100%);
  transition: height 0.7s cubic-bezier(0.22, 0.8, 0.36, 1);
}
.day-label { font-size: 11px; color: var(--ink-3); }
.day-count { font-size: 11.5px; font-weight: 700; color: var(--ink-2); }

.mastery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(86px, 1fr));
  gap: 10px;
}
.mastery-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 14px 6px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.mastery-count {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  color: var(--ink);
}
.mastery-level { font-size: 11.5px; color: var(--ink-3); }

/* 环形图 */
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
  transform: rotate(0deg);
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
  transition: stroke-dasharray 0.9s cubic-bezier(0.22, 0.8, 0.36, 1);
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
.legend-name { color: var(--ink-2); }
.legend-num { margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }
.legend-pct { color: var(--ink-3); font-size: 12px; width: 38px; text-align: right; }

.bar-row {
  display: grid;
  grid-template-columns: 150px 1fr 110px;
  align-items: center;
  gap: 12px;
  padding: 7px 0;
}
@media (max-width: 560px) {
  .bar-row { grid-template-columns: 100px 1fr 90px; }
}
.bar-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-nums {
  font-size: 12px;
  color: var(--ink-3);
  text-align: right;
  white-space: nowrap;
}
.bar-nums .avg { margin-left: 6px; }

.plain-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
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
</style>
