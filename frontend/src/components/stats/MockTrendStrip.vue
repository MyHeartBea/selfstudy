<script setup>
/**
 * 模考成绩趋势条（[09]）：最近 12 场分数折线 + 场次芯片。
 * 数据随 /api/dashboard 聚合带回（旧后端无此字段时由父组件单独兜底拉取），纯展示。
 */
import { computed } from 'vue'

import GlassCard from '../../ui/GlassCard.vue'

const props = defineProps({
  mocks: { type: Array, default: () => [] },
})

const mockTrend = computed(() => {
  // 时间正序，取最近 12 场画折线
  return [...props.mocks].reverse().slice(-12)
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
</script>

<template>
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
</template>

<style scoped>
/* 条带头部：mock 条沿用 fc-head 类名（原主文件共享规则中 fc-head 的部分） */
.stats-page .fc-head {
  align-items: baseline;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(20px, 3vh, 36px);
}
.stats-page .fc-head .panel-title {
  font-size: 11.5px !important;
  letter-spacing: 0.2em !important;
  text-transform: uppercase !important;
  color: var(--ink-2) !important;
}
.stats-page .fc-head::before {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-right: 2px;
}

/* 条带本体 */
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
</style>
