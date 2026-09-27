<script setup>
/**
 * 复习负荷预报条（[03]）：未来 30 天到期分布，主 Bento 之下的横向条带。
 * 数据随 /api/dashboard 聚合带回（旧后端无此字段时由父组件单独兜底拉取），纯展示。
 */
import { computed } from 'vue'

import GlassCard from '../../ui/GlassCard.vue'

const props = defineProps({
  forecast: {
    type: Object,
    default: () => ({ overdue: 0, items: [] }),
  },
})

const forecastCols = computed(() => {
  const map = new Map((props.forecast.items || []).map((i) => [i.day, Number(i.count) || 0]))
  const out = []
  const today = new Date()
  for (let i = 0; i < 30; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() + i)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate(),
    ).padStart(2, '0')}`
    out.push({
      day: key,
      count: map.get(key) || 0,
      label: i === 0 ? '今天' : i % 7 === 0 ? `${d.getMonth() + 1}/${d.getDate()}` : '',
    })
  }
  return out
})
const forecastMax = computed(() => Math.max(1, ...forecastCols.value.map((c) => c.count)))
</script>

<template>
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
            height: (c.count ? Math.max(6, Math.round((c.count / forecastMax) * 64)) : 4) + 'px',
          }"
        ></i>
        <span class="fc-label num km-num">{{ c.label }}</span>
      </div>
    </div>
  </GlassCard>
</template>

<style scoped>
/* 条带头部（原主文件共享规则中 fc-head 的部分） */
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
  content: '[03]';
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-right: 2px;
}

/* 条带本体 */
.fc-strip {
  overflow: hidden;
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
</style>
