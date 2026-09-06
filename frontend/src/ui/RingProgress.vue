<script setup>
/**
 * SVG 进度环：渐变描边 + 弹性生长动画，中心内容走默认插槽。
 */
import { computed, onMounted, ref } from 'vue'

const props = defineProps({
  percentage: { type: Number, default: 0 },
  size: { type: Number, default: 150 },
  stroke: { type: Number, default: 9 },
  from: { type: String, default: 'var(--accent)' },
  to: { type: String, default: '#d0664c' },
})

const uid = `ring-${Math.random().toString(36).slice(2, 8)}`
const R = computed(() => (props.size - props.stroke) / 2 - 1)
const C = computed(() => 2 * Math.PI * R.value)
const shown = ref(0)

onMounted(() => {
  // 下一帧再给目标值，触发 dashoffset 过渡生长
  requestAnimationFrame(() => {
    shown.value = Math.min(100, Math.max(0, props.percentage))
  })
})
</script>

<template>
  <div class="ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`">
      <defs>
        <linearGradient :id="uid" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" :stop-color="from" />
          <stop offset="1" :stop-color="to" />
        </linearGradient>
      </defs>
      <circle class="ring-track" :cx="size / 2" :cy="size / 2" :r="R" :stroke-width="stroke" fill="none" />
      <circle
        class="ring-fill"
        :cx="size / 2"
        :cy="size / 2"
        :r="R"
        :stroke-width="stroke"
        fill="none"
        stroke-linecap="round"
        :stroke="`url(#${uid})`"
        :stroke-dasharray="C"
        :stroke-dashoffset="C * (1 - shown / 100)"
      />
    </svg>
    <div class="ring-center"><slot></slot></div>
  </div>
</template>

<style scoped>
.ring { position: relative; flex: none; }
.ring svg { transform: rotate(-90deg); display: block; }
.ring-track { stroke: var(--surface-2); }
.ring-fill { transition: stroke-dashoffset 1.2s var(--spring); }
.ring-center {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  text-align: center;
}
</style>
