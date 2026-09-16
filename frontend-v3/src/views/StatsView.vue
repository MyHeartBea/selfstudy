<!--
  StatsView —— 学习统计 · 成册
  ---------------------------------------------------------------------------
  语义：统计不是仪表盘，是把散落的笔迹**装订成册**。所以布局用非对称 Bento 网格，
  而不是等宽卡片墙；所有图形共用一套等宽刻度，读起来像仪器输出。

  契约（基线实测字段）：
    /api/stats        - total_mistakes / today_new / by_subject / by_sub_subject /
                        by_question_type / by_source_type
    /api/reviews/stats - due_today / reviewed_today / streak_days / avg_mastery /
                        total_accuracy / mastery_distribution / last_7_days / weakest_tags
  两个端点并发请求（互不依赖），用 Promise.allSettled 让其中一个失败也不空屏。
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { statsApi, reviewsApi } from '../core/api'
import { traceOnScroll } from '../design/motion'
import UiEmpty from '../ui/UiEmpty.vue'
import UiTag from '../ui/UiTag.vue'

const loading = ref(true)
const stats = ref(null)
const reviews = ref(null)
const errorText = ref('')
const curveHost = ref(null)

const mastery = computed(() => reviews.value?.mastery_distribution || [])
const masteryTotal = computed(() => mastery.value.reduce((a, x) => a + (x.count || 0), 0))
const subjects = computed(() => stats.value?.by_subject || [])
const maxSubject = computed(() => Math.max(1, ...subjects.value.map((s) => s.count || 0)))
const lessonTypes = computed(() => stats.value?.by_question_type || [])
const maxType = computed(() => Math.max(1, ...lessonTypes.value.map((t) => t.count || 0)))

/** 近 7 天复习量：归一成 SVG 折线（等宽刻度，底部基线） */
const week = computed(() => reviews.value?.last_7_days || [])
const W = 560
const H = 132
const weekPath = computed(() => {
  const list = week.value
  if (list.length < 2) return ''
  const max = Math.max(1, ...list.map((d) => d.count || 0))
  return list
    .map((d, i) => {
      const x = (i * W) / (list.length - 1)
      const y = H - 14 - ((d.count || 0) / max) * (H - 30)
      return `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})
const weekArea = computed(() => (weekPath.value ? `${weekPath.value} L${W},${H} L0,${H} Z` : ''))

/** 掌握度分布：五档墨柱（越高档越亮，与 InkDot 的语义一致） */
const masteryBars = computed(() => {
  const byLevel = new Map(mastery.value.map((m) => [Number(m.mastery ?? 0), m.count || 0]))
  const max = Math.max(1, ...byLevel.values())
  return Array.from({ length: 5 }, (_, i) => {
    const level = i * 20 + 20
    const count = byLevel.get(level) || byLevel.get(i + 1) || 0
    return { level, count, ratio: Math.round((count / max) * 100) }
  })
})

async function load() {
  loading.value = true
  errorText.value = ''
  const [s, r] = await Promise.allSettled([statsApi.overview(), reviewsApi.stats()])
  stats.value = s.status === 'fulfilled' ? s.value : null
  reviews.value = r.status === 'fulfilled' ? r.value : null
  if (s.status === 'rejected' && r.status === 'rejected') {
    errorText.value = s.reason?.message || '统计载入失败'
  }
  loading.value = false
}

onMounted(async () => {
  await load()
  // 折线在进入视口时按路径真实长度写出（描绘原语），不是裁剪遮罩
  traceOnScroll(curveHost.value)
})
</script>

<template>
  <main id="main" class="pad">
    <header class="head">
      <span class="mono">[05] BINDER · 学习统计</span>
      <span class="mono"
        >{{ stats?.total_mistakes ?? 0 }} 条错题 · 复习 {{ reviews?.total_reviews ?? 0 }} 次</span
      >
    </header>

    <UiEmpty v-if="loading" variant="skeleton" :rows="4" />
    <UiEmpty v-else-if="errorText" title="统计载入失败" :hint="errorText" />

    <template v-else>
      <div class="binder">
        <!-- 英雄格：今日待复习（最重要，占两列） -->
        <section class="leaf hero">
          <span class="mono lab">Today · 今日待复习</span>
          <div class="big num">{{ reviews?.due_today ?? 0 }}</div>
          <p class="sub">
            今日已复习 <b>{{ reviews?.reviewed_today ?? 0 }}</b> 题 · 连续
            <b>{{ reviews?.streak_days ?? 0 }}</b> 天
          </p>
        </section>

        <section class="leaf">
          <span class="mono lab">Accuracy · 正确率</span>
          <div class="big num">{{ Math.round(reviews?.total_accuracy ?? 0) }}<em>%</em></div>
          <p class="sub">近 30 天 · 今日 {{ Math.round(reviews?.accuracy_today ?? 0) }}%</p>
        </section>

        <section class="leaf">
          <span class="mono lab">Mastery · 平均掌握度</span>
          <div class="big num">{{ Math.round(reviews?.avg_mastery ?? 0) }}<em>%</em></div>
          <p class="sub">今日新增 {{ stats?.today_new ?? 0 }} 题</p>
        </section>

        <!-- 光变曲线（描绘 + 面积填充） -->
        <section ref="curveHost" class="leaf wide trace-host">
          <span class="mono lab">Light curve · 近 7 天复习量</span>
          <svg
            v-if="weekPath"
            :viewBox="`0 0 ${W} ${H}`"
            preserveAspectRatio="none"
            class="curve"
            role="img"
            aria-label="近 7 天复习量走势"
          >
            <path class="trace-area" :d="weekArea" />
            <path class="trace-path" :d="weekPath" />
          </svg>
          <p v-else class="sub">数据不足两天，暂无曲线</p>
          <div class="xaxis mono">
            <span v-for="d in week" :key="d.day">{{ (d.day || '').slice(5) }}</span>
          </div>
        </section>

        <!-- 掌握度分布：墨柱 -->
        <section class="leaf">
          <span class="mono lab">Mastery spread · 掌握度分布</span>
          <div class="bars">
            <div v-for="b in masteryBars" :key="b.level" class="bar">
              <i :style="{ height: Math.max(4, b.ratio) + '%' }" :data-l="b.level"></i>
              <span class="mono bnum">{{ b.count }}</span>
            </div>
          </div>
          <p class="sub">共 {{ masteryTotal }} 题入库</p>
        </section>

        <!-- 科目分布 -->
        <section class="leaf wide">
          <span class="mono lab">By subject · 科目分布</span>
          <div v-if="subjects.length" class="rows">
            <div v-for="s in subjects" :key="s.subject_id" class="rrow">
              <span class="rname">{{ s.name }}</span>
              <span class="rtrack"
                ><i :style="{ width: Math.round(((s.count || 0) / maxSubject) * 100) + '%' }"></i
              ></span>
              <span class="mono rnum">{{ s.count }}</span>
            </div>
          </div>
          <p v-else class="sub">暂无科目数据</p>
        </section>

        <!-- 题型分布 -->
        <section class="leaf">
          <span class="mono lab">By type · 题型</span>
          <div v-if="lessonTypes.length" class="rows">
            <div v-for="t in lessonTypes" :key="t.question_type" class="rrow">
              <span class="rname">{{ t.name || t.question_type }}</span>
              <span class="rtrack"
                ><i :style="{ width: Math.round(((t.count || 0) / maxType) * 100) + '%' }"></i
              ></span>
              <span class="mono rnum">{{ t.count }}</span>
            </div>
          </div>
          <p v-else class="sub">暂无题型数据</p>
        </section>

        <!-- 薄弱知识点 -->
        <section class="leaf">
          <span class="mono lab">Weakest · 薄弱知识点</span>
          <div v-if="(reviews?.weakest_tags || []).length" class="chips">
            <UiTag
              v-for="t in reviews.weakest_tags.slice(0, 8)"
              :key="t.tag_name"
              tone="red-shift"
              size="sm"
            >
              {{ t.tag_name }}<span class="mono cn">{{ t.mistake_count }}</span>
            </UiTag>
          </div>
          <p v-else class="sub">还没有足够的复习记录</p>
        </section>
      </div>
    </template>
  </main>
</template>

<style scoped>
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

/* 非对称 Bento：12 列，英雄格跨 5 列 */
.binder {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.leaf {
  grid-column: span 3;
  background: var(--sky-1);
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.leaf.hero {
  grid-column: span 6;
  background: var(--sky-2);
}
.leaf.wide {
  grid-column: span 6;
}
.lab {
  color: var(--ink-3);
}
.big {
  font-family: var(--font-mono);
  font-weight: 300;
  font-size: clamp(2rem, 4vw, 3.2rem);
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--ink-0);
}
.big em {
  font-style: normal;
  font-size: 0.42em;
  color: var(--ink-2);
  margin-left: 3px;
}
.sub {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  line-height: 1.7;
}
.sub b {
  color: var(--ink-0);
  font-weight: 500;
}

/* 曲线 */
.curve {
  width: 100%;
  height: 132px;
  display: block;
  margin-top: 6px;
}
.xaxis {
  display: flex;
  justify-content: space-between;
  color: var(--ink-3);
  margin-top: 4px;
}

/* 掌握度墨柱 */
.bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 96px;
  margin-top: 8px;
}
.bar {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: center;
  height: 100%;
  gap: 5px;
}
.bar i {
  width: 100%;
  background: var(--sky-3);
  transition: height 0.9s var(--e-settle);
}
/* 档位越高越亮：与 InkDot 的"墨色沉淀"语义一致 */
.bar i[data-l='20'] {
  background: color-mix(in srgb, var(--ink-0) 24%, var(--sky-3));
}
.bar i[data-l='40'] {
  background: color-mix(in srgb, var(--ink-0) 40%, var(--sky-3));
}
.bar i[data-l='60'] {
  background: color-mix(in srgb, var(--ink-0) 62%, var(--sky-3));
}
.bar i[data-l='80'] {
  background: color-mix(in srgb, var(--ink-0) 82%, var(--sky-3));
}
.bar i[data-l='100'] {
  background: var(--ink-0);
}
.bnum {
  color: var(--ink-3);
}

/* 分布行：等宽刻度条 */
.rows {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 6px;
}
.rrow {
  display: grid;
  grid-template-columns: minmax(74px, auto) minmax(0, 1fr) 40px;
  align-items: center;
  gap: 10px;
  font-size: var(--fs-sm);
}
.rname {
  color: var(--ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rtrack {
  height: 8px;
  background: var(--sky-0);
  border: 1px solid var(--line);
}
.rtrack i {
  display: block;
  height: 100%;
  background: var(--vein);
}
.rnum {
  text-align: right;
  color: var(--ink-2);
}
.chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 6px;
}
.chips .cn {
  margin-left: 6px;
  opacity: 0.7;
}

@media (max-width: 1000px) {
  .leaf,
  .leaf.wide,
  .leaf.hero {
    grid-column: span 6;
  }
}
@media (max-width: 640px) {
  .leaf,
  .leaf.wide,
  .leaf.hero {
    grid-column: span 12;
  }
}
</style>
