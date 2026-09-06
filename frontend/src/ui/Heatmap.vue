<script setup>
/**
 * 复习热力图：周列 × 7 行，墨色深浅 = 当日复习量，格子级联入场。
 * data = [{ date: 'YYYY-MM-DD', count: Number }]，按时间升序；
 * 内部补齐首尾到整周；列上限 maxWeeks（默认 18 周）时裁掉最早的。
 */
import { computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  maxWeeks: { type: Number, default: 18 },
})

const TIPS = ['未复习', '1-2 题', '3-5 题', '6-9 题', '10+ 题']

function levelOf(count) {
  const c = Number(count) || 0
  if (c <= 0) return 0
  if (c <= 2) return 1
  if (c <= 5) return 2
  if (c <= 9) return 3
  return 4
}

// 补齐成整周并裁剪到 maxWeeks
const weeks = computed(() => {
  const map = new Map(props.data.map((d) => [d.date, Number(d.count) || 0]))
  const list = []
  if (props.data.length) {
    const first = new Date(props.data[0].date + 'T00:00:00')
    first.setDate(first.getDate() - ((first.getDay() + 6) % 7)) // 回到周一
    const last = new Date(props.data[props.data.length - 1].date + 'T00:00:00')
    for (const d = new Date(first); d <= last; d.setDate(d.getDate() + 1)) {
      const key = d.toISOString().slice(0, 10)
      list.push({ date: key, count: map.get(key) || 0 })
    }
  }
  const trimmed = list.slice(-props.maxWeeks * 7)
  const cols = []
  for (let i = 0; i < trimmed.length; i += 7) cols.push(trimmed.slice(i, i + 7))
  return cols
})

const months = computed(() => {
  // 每列取首日，月份变化处打标
  const marks = []
  let last = -1
  weeks.value.forEach((col, ci) => {
    if (!col.length) return
    const m = new Date(col[0].date + 'T00:00:00').getMonth()
    if (m !== last) {
      marks.push({ index: ci, label: `${m + 1}月` })
      last = m
    }
  })
  return marks
})

const dayIndex = (ci, ri) => ci * 7 + ri
</script>

<template>
  <div class="heatmap-wrap">
    <div class="heatmap" :style="{ '--cols': weeks.length }">
      <template v-for="(col, ci) in weeks" :key="ci">
        <span
          v-for="(cell, ri) in col"
          :key="cell.date"
          class="hm-cell"
          :class="`hm-${levelOf(cell.count)}`"
          :style="{ '--i': dayIndex(ci, ri) }"
          :title="`${cell.date}：复习 ${cell.count} 题`"
        ></span>
      </template>
    </div>
    <div class="hm-months">
      <span v-for="m in months" :key="m.index" class="hm-month" :style="{ left: ((m.index + 0.5) / weeks.length) * 100 + '%' }">{{ m.label }}</span>
    </div>
    <div class="hm-scale">
      少 <i class="hm-cell hm-0"></i><i class="hm-cell hm-1"></i><i class="hm-cell hm-2"></i><i class="hm-cell hm-3"></i><i class="hm-cell hm-4"></i> 多
    </div>
  </div>
</template>

<style scoped>
.heatmap-wrap { min-width: 0; }
.heatmap {
  display: grid;
  grid-template-rows: repeat(7, 10px);
  grid-auto-flow: column;
  grid-auto-columns: 10px;
  gap: 3.5px;
  justify-content: space-between;
}
.hm-cell {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  opacity: 0;
  transform: scale(0.2);
  animation: hm-in 0.5s var(--spring) forwards;
  animation-delay: calc(var(--i) * 4.5ms);
  transition: transform 0.15s var(--spring);
}
@keyframes hm-in { to { opacity: 1; transform: scale(1); } }
.hm-cell:hover { transform: scale(1.5) !important; }
.hm-0 { background: var(--surface-2); }
.hm-1 { background: color-mix(in srgb, var(--ink) 10%, var(--surface-2)); }
.hm-2 { background: color-mix(in srgb, var(--ink) 24%, var(--surface-2)); }
.hm-3 { background: color-mix(in srgb, var(--ink) 45%, var(--surface-2)); }
.hm-4 { background: var(--accent); box-shadow: 0 0 0 1px var(--accent-ring); }

.hm-months {
  position: relative;
  height: 16px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--ink-3);
}
.hm-month { position: absolute; top: 2px; transform: translateX(-50%); }

.hm-scale {
  display: flex;
  align-items: center;
  gap: 3.5px;
  justify-content: flex-end;
  margin-top: 2px;
  font-size: 11px;
  color: var(--ink-3);
}
.hm-scale .hm-cell {
  opacity: 1;
  transform: none;
  animation: none;
  display: inline-block;
}
</style>
