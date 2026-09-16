<!--
  MocksView —— 模考记录
  ---------------------------------------------------------------------------
  语义：模考 = 一次实际观测；得分曲线 = 观测质量随时间的走向。

  契约（基线实测）：
    GET /api/mocks?limit=N - [{ id, exam_year, total, correct, score,
                                duration_min, used_seconds, created_at }]
    score 已是百分制（后端算好），前端不再重复计算 —— 避免两处口径不一致。

  设计取舍：分数用**横向等宽刻度条 + 数值**，不用环形图：
  模考次数少，横向对比比"漂亮的圆环"更能看出波动。
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { mocksApi } from '../core/api/extra'
import { traceOnScroll } from '../design/motion'
import { usePageMotion } from '../design/usePageMotion'
import UiEmpty from '../ui/UiEmpty.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const loading = ref(true)
const errorText = ref('')
const items = ref([])
const curveHost = ref(null)

/** 后端按时间倒序给，画曲线需要正序 */
const series = computed(() => [...items.value].reverse())

const avgScore = computed(() => {
  if (!items.value.length) return 0
  const sum = items.value.reduce((a, m) => a + (m.score || 0), 0)
  return Math.round(sum / items.value.length)
})
const bestScore = computed(() => Math.max(0, ...items.value.map((m) => m.score || 0)))

/** 得分曲线：等宽刻度 + 真实路径长度描绘 */
const W = 640
const H = 150
const curvePath = computed(() => {
  const list = series.value
  if (list.length < 2) return ''
  return list
    .map((m, i) => {
      const x = (i * W) / (list.length - 1)
      const y = H - 16 - ((m.score || 0) / 100) * (H - 32)
      return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

/** 用时：used_seconds 优先，否则回落到 duration_min */
function usedText(m) {
  if (m.used_seconds) {
    const min = Math.floor(m.used_seconds / 60)
    const sec = Math.round(m.used_seconds % 60)
    return `${min} 分 ${String(sec).padStart(2, '0')} 秒`
  }
  return m.duration_min ? `${m.duration_min} 分钟` : '未记录'
}

function toneOf(score) {
  if (score >= 80) return 'vein'
  if (score >= 60) return 'gold'
  return 'red-shift'
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    items.value = (await mocksApi.list(24)) || []
  } catch (e) {
    errorText.value = e?.message || '无法载入模考记录'
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  traceOnScroll(curveHost.value)
})
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <h1 class="mono page-h1">模考记录</h1>
      <span class="mono">{{ items.length }} 次 · 均分 {{ avgScore }} · 最好 {{ bestScore }}</span>
    </header>

    <UiEmpty v-if="loading" variant="skeleton" :rows="4" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty
      v-else-if="!items.length"
      title="还没有模考记录"
      hint="完成一次模考后，这里会出现得分走势"
    />

    <template v-else>
      <!-- 摘要：三个读数 -->
      <div class="stats reveal" data-reveal>
        <div class="st">
          <span class="mono lab">均分</span>
          <span class="num big">{{ avgScore }}</span>
        </div>
        <div class="st">
          <span class="mono lab">最高</span>
          <span class="num big">{{ bestScore }}</span>
        </div>
        <div class="st">
          <span class="mono lab">最近一次</span>
          <span class="num big">{{ items[0]?.score ?? '—' }}</span>
        </div>
      </div>

      <!-- 得分曲线（描绘原语） -->
      <section ref="curveHost" class="curve-wrap trace-host reveal" data-reveal>
        <span class="mono lab">得分走势（时间正序）</span>
        <svg
          v-if="curvePath"
          :viewBox="`0 0 ${W} ${H}`"
          preserveAspectRatio="none"
          class="curve"
          role="img"
          aria-label="模考得分走势"
        >
          <path class="trace-path" :d="curvePath" />
        </svg>
        <p v-else class="mono hint">至少两次记录才能画出走势</p>
      </section>

      <!-- 记录表：分数用等宽刻度条，便于横向比较波动 -->
      <div class="rows reveal" data-reveal>
        <div v-for="m in items" :key="m.id" class="row">
          <span class="mono when">{{ (m.created_at || '').slice(0, 16).replace('T', ' ') }}</span>
          <span class="mono yr">{{ m.exam_year || '—' }}</span>
          <span class="track" aria-hidden="true">
            <i
              :style="{ width: Math.max(2, m.score || 0) + '%' }"
              :data-t="toneOf(m.score || 0)"
            ></i>
          </span>
          <span class="num sc">{{ m.score ?? '—' }}</span>
          <span class="mono detail"> {{ m.correct || 0 }} / {{ m.total || 0 }} </span>
          <span class="mono used">{{ usedText(m) }}</span>
          <UiTag :tone="toneOf(m.score || 0)" size="sm">
            {{ (m.score || 0) >= 80 ? '稳定' : (m.score || 0) >= 60 ? '及格' : '需加强' }}
          </UiTag>
        </div>
      </div>
    </template>
  </main>
</template>

<style scoped>
.page-h1 {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  font-weight: 400;
  letter-spacing: 0.12em;
  margin: 0;
}
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 30px);
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
  margin-bottom: 18px;
}
.st {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 15px 18px;
  background: var(--sky-1);
}
.lab {
  color: var(--ink-3);
}
.big {
  font-size: clamp(1.6rem, 3.4vw, 2.6rem);
}
.num {
  font-family: var(--font-mono);
  font-weight: 300;
  color: var(--ink-0);
  letter-spacing: -0.03em;
  line-height: 1;
}
.curve-wrap {
  padding: 16px 18px 12px;
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin-bottom: 18px;
}
.curve {
  width: 100%;
  height: 150px;
  display: block;
  margin-top: 8px;
}
.hint {
  color: var(--ink-3);
  margin-top: 6px;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.row {
  display: grid;
  grid-template-columns: 118px 62px minmax(0, 1fr) 46px 66px 92px auto;
  gap: 12px;
  align-items: center;
  padding: 11px 14px;
  background: var(--sky-1);
  font-size: var(--fs-sm);
}
.row:hover {
  background: var(--sky-2);
}
.when,
.yr,
.detail,
.used {
  color: var(--ink-3);
}
.track {
  height: 8px;
  background: var(--sky-0);
  border: 1px solid var(--line);
}
.track i {
  display: block;
  height: 100%;
  background: var(--vein);
  transition: width 0.8s var(--e-settle);
}
.track i[data-t='gold'] {
  background: var(--gold);
}
.track i[data-t='red-shift'] {
  background: var(--redshift);
}
.sc {
  text-align: right;
  color: var(--ink-0);
}

@media (max-width: 900px) {
  .row {
    grid-template-columns: 1fr auto;
    row-gap: 5px;
  }
  .track {
    grid-column: 1 / -1;
  }
  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
