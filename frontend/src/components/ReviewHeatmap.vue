<script setup>
/** 复习热力图：GitHub 风格日历格子，按周分列，色阶表示当天复习量。 */
import { computed, onMounted, ref } from 'vue'

import request from '../api/request'

const props = defineProps({
  days: { type: Number, default: 119 }, // 17 周
})

const records = ref([])
const loading = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await request.get('/reviews/calendar', { params: { days: props.days } })
    records.value = res.data.data || []
  } catch (err) {
    records.value = []
  } finally {
    loading.value = false
  }
}

function toDateStr(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

// 构建从最早一周的周一开始、到今天为止的格子矩阵（响应式）
const WEEK_LABELS = ['一', '', '三', '', '五', '', '日']

const heat = computed(() => {
  const map = new Map()
  for (const r of records.value) map.set(r.day, r)
  const today = new Date()
  const todayStr = toDateStr(today)

  // 起点：days-1 天前所在周的周一
  const start = new Date(today)
  start.setDate(start.getDate() - (props.days - 1))
  const startWeekMonday = new Date(start)
  const dow = (start.getDay() + 6) % 7 // 0=周一
  startWeekMonday.setDate(start.getDate() - dow)

  const weeks = []
  const monthMarks = []
  let cursor = new Date(startWeekMonday)
  let lastMonth = -1
  const today0 = new Date(todayStr + 'T00:00:00')

  while (cursor <= today0) {
    const col = []
    for (let d = 0; d < 7; d++) {
      const dayDate = new Date(cursor)
      dayDate.setDate(cursor.getDate() + d)
      const dayStr = toDateStr(dayDate)
      const future = dayDate > today0
      const record = map.get(dayStr)
      col.push({
        day: dayStr,
        future,
        total: record ? record.total : 0,
        correct: record ? record.correct : 0,
      })
      // 月份标记（每列第一天的月份变化时）
      if (d === 0 && dayDate.getMonth() !== lastMonth) {
        lastMonth = dayDate.getMonth()
        monthMarks.push({ index: weeks.length, label: `${lastMonth + 1}月` })
      }
    }
    weeks.push(col)
    cursor.setDate(cursor.getDate() + 7)
  }

  let totalActive = 0
  let totalCount = 0
  for (const r of records.value) {
    if (r.total > 0) totalActive += 1
    totalCount += r.total
  }
  return { weeks, monthMarks, totalActive, totalCount }
})

const weekCount = computed(() => heat.value.weeks.length)
const todayStr = ref(toDateStr(new Date()))

function level(cell) {
  if (!cell || cell.future) return -1
  if (!cell.total) return 0
  if (cell.total <= 2) return 1
  if (cell.total <= 5) return 2
  if (cell.total <= 10) return 3
  return 4
}

function title(cell) {
  if (!cell) return ''
  if (cell.future) return ''
  return `${cell.day}：复习 ${cell.total} 题${cell.total ? `，答对 ${cell.correct}` : ''}`
}
</script>

<template>
  <div class="heatmap" :class="{ loading }">
    <div class="hm-canvas">
      <div class="hm-weeks">
        <span v-for="(label, i) in WEEK_LABELS" :key="i" class="hm-week-label">{{ label }}</span>
      </div>
      <div class="hm-grid-wrap">
        <div class="hm-months" :style="{ gridTemplateColumns: `repeat(${weekCount}, 1fr)` }">
          <span
            v-for="mark in heat.monthMarks"
            :key="mark.index + mark.label"
            class="hm-month"
            :style="{ gridColumnStart: mark.index + 1 }"
          >{{ mark.label }}</span>
        </div>
        <div class="hm-grid" :style="{ gridTemplateColumns: `repeat(${weekCount}, 1fr)` }">
          <template v-for="(week, wi) in heat.weeks" :key="wi">
            <div
              v-for="cell in week"
              :key="cell.day"
              class="hm-cell"
              :class="[`lv-${level(cell)}`, { future: cell.future, today: cell.day === todayStr }]"
              :title="title(cell)"
            ></div>
          </template>
        </div>
      </div>
    </div>
    <div class="hm-foot">
      <span class="count-tip">近 {{ days }} 天复习 {{ heat.totalCount }} 次 · {{ heat.totalActive }} 个活跃日</span>
      <span class="hm-legend">
        少
        <i class="hm-cell lv-0"></i>
        <i class="hm-cell lv-1"></i>
        <i class="hm-cell lv-2"></i>
        <i class="hm-cell lv-3"></i>
        <i class="hm-cell lv-4"></i>
        多
      </span>
    </div>
  </div>
</template>

<style scoped>
.heatmap { display: flex; flex-direction: column; gap: 12px; }

.hm-canvas {
  display: flex;
  gap: 8px;
}

.hm-weeks {
  display: grid;
  grid-template-rows: repeat(7, 13px);
  gap: 3px;
  padding-top: 18px;
  flex: none;
}
.hm-week-label {
  font-size: 9.5px;
  color: var(--ink-3);
  line-height: 13px;
  height: 13px;
}

.hm-grid-wrap { flex: 1; min-width: 0; overflow-x: auto; }

.hm-months {
  display: grid;
  height: 15px;
  margin-bottom: 3px;
  min-width: fit-content;
}
.hm-month {
  font-size: 10px;
  color: var(--ink-3);
  white-space: nowrap;
  grid-column: span 1;
}

.hm-grid {
  display: grid;
  grid-auto-flow: column;
  grid-template-rows: repeat(7, 13px);
  gap: 3px;
  min-width: fit-content;
}

.hm-cell {
  width: 13px;
  height: 13px;
  border-radius: 3.5px;
  background: var(--bg-soft);
  transition: transform 0.12s;
}
.hm-cell:hover { transform: scale(1.35); }
.hm-cell.future { background: transparent; }
.hm-cell.today { outline: 1.5px solid var(--accent); outline-offset: 1px; }
.hm-cell.lv-0 { background: var(--bg-soft); }
.hm-cell.lv-1 { background: color-mix(in srgb, var(--accent) 28%, var(--bg-soft)); }
.hm-cell.lv-2 { background: color-mix(in srgb, var(--accent) 52%, transparent); }
.hm-cell.lv-3 { background: color-mix(in srgb, var(--accent) 76%, transparent); }
.hm-cell.lv-4 { background: var(--accent); }

.hm-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.hm-legend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10.5px;
  color: var(--ink-3);
}
.hm-legend .hm-cell { width: 11px; height: 11px; }
</style>
