<script setup>
/**
 * 手写 SVG 面积图（零依赖）：双系列折线 + 渐变面积 + 数据点弹入。
 * 颜色直接引用 CSS 变量，深浅主题切换自动跟随，无需重绘。
 * series = [{ name, color: 'var(--accent)', values: [..] }]
 */
import { computed } from 'vue'

const props = defineProps({
  labels: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  height: { type: Number, default: 210 },
  legend: { type: Boolean, default: true },
})

const W = 560
const H = computed(() => props.height)
const PAD = 34

const n = computed(() => Math.max(props.labels.length, ...props.series.map((s) => s.values.length), 1))
const maxValue = computed(() => {
  const all = props.series.flatMap((s) => s.values).filter((v) => Number.isFinite(v))
  if (!all.length) return 10
  const max = Math.max(...all)
  const step = max > 40 ? 10 : max > 12 ? 5 : max > 6 ? 3 : 2
  return Math.max(step, Math.ceil(max / step) * step)
})

const xs = (i) => PAD + (i * (W - 2 * PAD)) / Math.max(1, n.value - 1)
const ys = (v) => H.value - 30 - (v / maxValue.value) * (H.value - 70)

const gridLines = computed(() => {
  const rows = []
  for (let g = 0; g <= 3; g++) {
    const y = H.value - 30 - (g * (H.value - 70)) / 3
    rows.push(y)
  }
  return rows
})

function pathOf(values) {
  return values.map((v, i) => `${i ? 'L' : 'M'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(' ')
}

const uid = `area-${Math.random().toString(36).slice(2, 8)}`
</script>

<template>
  <div class="area-chart">
    <svg :viewBox="`0 0 ${W} ${H}`" width="100%" :style="{ display: 'block' }" role="img" aria-label="趋势图">
      <defs>
        <linearGradient v-for="(s, si) in series" :key="si" :id="`${uid}-${si}`" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" :stop-color="s.color" stop-opacity="0.22" />
          <stop offset="1" :stop-color="s.color" stop-opacity="0" />
        </linearGradient>
      </defs>

      <line
        v-for="(y, gi) in gridLines"
        :key="gi"
        :x1="PAD" :y1="y" :x2="W - PAD" :y2="y"
        stroke="var(--line)" stroke-width="1"
      />

      <g v-for="(s, si) in series" :key="s.name">
        <path
          v-if="s.values.length > 1"
          class="ac-area"
          :d="`${pathOf(s.values)} L${xs(s.values.length - 1)},${H - 30} L${xs(0)},${H - 30} Z`"
          :fill="`url(#${uid}-${si})`"
          :style="{ animationDelay: 0.15 + si * 0.2 + 's' }"
        />
        <path
          v-if="s.values.length > 1"
          class="ac-line"
            :d="pathOf(s.values)"
          fill="none"
          :stroke="s.color"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          pathLength="1"
          :style="{ animationDelay: 0.15 + si * 0.2 + 's' }"
        />
        <circle
          v-for="(v, i) in s.values"
          :key="i"
          class="ac-dot"
          :cx="xs(i)" :cy="ys(v)" r="3.5"
          fill="var(--surface)"
          :stroke="s.color"
          stroke-width="2.2"
          :style="{ animationDelay: 0.35 + si * 0.2 + i * 0.07 + 's' }"
        />
      </g>

      <text
        v-for="(label, i) in labels"
        :key="'l' + i"
        :x="xs(i)" :y="H - 8"
        text-anchor="middle" font-size="11"
        fill="var(--ink-3)"
      >{{ label }}</text>
    </svg>

    <div v-if="legend && series.length" class="ac-legend">
      <span v-for="s in series" :key="s.name"><i :style="{ background: s.color }"></i>{{ s.name }}</span>
    </div>
  </div>
</template>

<style scoped>
.ac-line {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: ac-draw 1.3s var(--ease) forwards;
}
@keyframes ac-draw { to { stroke-dashoffset: 0; } }

.ac-area { opacity: 0; animation: ac-fade 0.9s var(--ease) forwards; }
@keyframes ac-fade { to { opacity: 1; } }

.ac-dot {
  opacity: 0;
  transform-box: fill-box;
  transform-origin: center;
  animation: ac-pop 0.45s var(--spring) forwards;
}
@keyframes ac-pop {
  from { opacity: 0; transform: scale(0.3); }
  to { opacity: 1; transform: scale(1); }
}

.ac-legend {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--ink-3);
  margin-top: 8px;
}
.ac-legend i {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 3px;
  margin-right: 5px;
  vertical-align: -1px;
}
</style>
