<script setup>
/** 复习日历：按月查看「哪天复习了多少 / 哪天到期多少」。过去看复习量，未来看到期负荷。 */
import { computed, onMounted, ref } from 'vue'

import request from '../api/request'
import Icon from '../ui/Icon.vue'

const past = ref([]) // [{day, total, correct}]
const dueMap = ref(new Map()) // day -> 到期题数
const loading = ref(false)

const today = new Date()
const cursor = ref({ year: today.getFullYear(), month: today.getMonth() })

onMounted(load)

async function load() {
  loading.value = true
  try {
    const [calRes, fcRes] = await Promise.all([
      request.get('/reviews/calendar', { params: { days: 366 } }),
      request.get('/reviews/forecast', { params: { days: 90 } }),
    ])
    past.value = calRes.data.data || []
    const map = new Map()
    for (const item of fcRes.data.data?.items || []) map.set(item.day, item.count)
    dueMap.value = map
  } catch (err) {
    past.value = []
  } finally {
    loading.value = false
  }
}

function pad(n) {
  return String(n).padStart(2, '0')
}
function dayStr(year, month, day) {
  return `${year}-${pad(month + 1)}-${pad(day)}`
}

const pastMap = computed(() => {
  const map = new Map()
  for (const r of past.value) map.set(r.day, r)
  return map
})

const monthTitle = computed(() => `${cursor.value.year} 年 ${cursor.value.month + 1} 月`)

const cells = computed(() => {
  const { year, month } = cursor.value
  const first = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const lead = (first.getDay() + 6) % 7 // 周一打头
  const today0 = new Date(today.getFullYear(), today.getMonth(), today.getDate())

  const list = []
  // 上月尾巴（补齐第一行，保持日期可读）
  for (let i = lead - 1; i >= 0; i--) {
    const d = new Date(year, month, -i)
    list.push(makeCell(d, today0, true))
  }
  for (let day = 1; day <= daysInMonth; day++) {
    list.push(makeCell(new Date(year, month, day), today0, false))
  }
  // 下月开头补齐最后一行
  while (list.length % 7 !== 0) {
    const d = new Date(year, month + 1, list.length - lead - daysInMonth + 1)
    list.push(makeCell(d, today0, true))
  }
  return list
})

function makeCell(date, today0, outside) {
  const key = dayStr(date.getFullYear(), date.getMonth(), date.getDate())
  const record = pastMap.value.get(key)
  const isFuture = date > today0
  return {
    key,
    day: date.getDate(),
    outside,
    isToday: date.getTime() === today0.getTime(),
    isFuture,
    total: record ? record.total : 0,
    correct: record ? record.correct : 0,
    due: isFuture ? dueMap.value.get(key) || 0 : 0,
  }
}

const canGoPrev = computed(() => {
  const months =
    (today.getFullYear() - cursor.value.year) * 12 + today.getMonth() - cursor.value.month
  return months < 11
})
const canGoNext = computed(() => {
  const months =
    (cursor.value.year - today.getFullYear()) * 12 + cursor.value.month - today.getMonth()
  return months < 2 // 预报只取 90 天，翻太远没有数据
})

function shiftMonth(delta) {
  const next = new Date(cursor.value.year, cursor.value.month + delta, 1)
  cursor.value = { year: next.getFullYear(), month: next.getMonth() }
}

const monthDone = computed(() => {
  const { year, month } = cursor.value
  const prefix = `${year}-${pad(month + 1)}-`
  let total = 0
  let active = 0
  for (const r of past.value) {
    if (String(r.day).startsWith(prefix)) {
      total += r.total
      if (r.total > 0) active += 1
    }
  }
  return { total, active }
})
</script>

<template>
  <div class="cal" :class="{ loading }">
    <div class="cal-head">
      <button
        type="button"
        class="cal-nav"
        :disabled="!canGoPrev"
        aria-label="上个月"
        @click="shiftMonth(-1)"
      >
        <Icon name="chevron-left" :size="14" />
      </button>
      <span class="cal-month serif">{{ monthTitle }}</span>
      <button
        type="button"
        class="cal-nav"
        :disabled="!canGoNext"
        aria-label="下个月"
        @click="shiftMonth(1)"
      >
        <Icon name="chevron-right" :size="14" />
      </button>
      <span class="cal-sum count-tip">
        本月复习 {{ monthDone.total }} 次 · {{ monthDone.active }} 个活跃日
      </span>
    </div>

    <div class="cal-grid">
      <span
        v-for="label in ['一', '二', '三', '四', '五', '六', '日']"
        :key="label"
        class="cal-wd"
        >{{ label }}</span
      >
      <div
        v-for="cell in cells"
        :key="cell.key"
        class="cal-cell"
        :class="{
          outside: cell.outside,
          today: cell.isToday,
          future: cell.isFuture,
          has: cell.total > 0,
          due: cell.due > 0,
        }"
        :title="`${cell.key}${cell.total ? `：复习 ${cell.total} 题，答对 ${cell.correct}` : ''}${
          cell.due ? `：到期 ${cell.due} 题` : ''
        }`"
      >
        <span class="cd num">{{ cell.day }}</span>
        <span v-if="cell.total > 0" class="cv done num">{{ cell.total }}</span>
        <span v-else-if="cell.due > 0" class="cv due num">{{ cell.due }}</span>
      </div>
    </div>

    <div class="cal-foot">
      <span class="cf-item"><i class="sw done"></i>复习题数</span>
      <span class="cf-item"><i class="sw due"></i>未来到期</span>
      <span class="cf-item"><i class="sw today"></i>今天</span>
    </div>
  </div>
</template>

<style scoped>
.cal {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cal-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cal-nav {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  cursor: pointer;
  transition:
    border-color var(--dur-1) var(--ease),
    color var(--dur-1) var(--ease);
}
.cal-nav:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-ink);
}
.cal-nav:disabled {
  opacity: 0.35;
  cursor: default;
}
.cal-month {
  font-size: 15px;
  font-weight: 700;
}
.cal-sum {
  margin-left: auto;
}

.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}
.cal-wd {
  text-align: center;
  font-size: 10.5px;
  color: var(--ink-3);
  padding-bottom: 2px;
}
.cal-cell {
  min-height: 46px;
  padding: 4px 6px;
  border-radius: 8px;
  background: var(--bg-soft);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  box-shadow: inset 0 0 0 1px var(--line);
  transition:
    background var(--dur-2) var(--ease),
    box-shadow var(--dur-2) var(--ease);
}
.cal-cell.outside {
  opacity: 0.45;
}
.cal-cell.today {
  box-shadow: inset 0 0 0 1.5px var(--accent);
}
.cal-cell.has {
  background: color-mix(in srgb, var(--accent) 16%, var(--bg-soft));
}
.cal-cell.future.due {
  background: color-mix(in srgb, var(--gold) 18%, var(--bg-soft));
}
.cd {
  font-size: 11px;
  color: var(--ink-3);
  line-height: 1.2;
}
.cv {
  font-size: 12.5px;
  font-weight: 800;
  line-height: 1.3;
}
.cv.done {
  color: var(--accent-ink);
}
.cv.due {
  color: var(--gold);
}

.cal-foot {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 11px;
  color: var(--ink-3);
}
.cf-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.sw {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
.sw.done {
  background: color-mix(in srgb, var(--accent) 30%, var(--bg-soft));
}
.sw.due {
  background: color-mix(in srgb, var(--gold) 35%, var(--bg-soft));
}
.sw.today {
  box-shadow: inset 0 0 0 1.5px var(--accent);
  background: var(--bg-soft);
}

@media (max-width: 720px) {
  .cal-cell {
    min-height: 36px;
    padding: 2px 4px;
  }
  .cal-sum {
    display: none;
  }
}
</style>
