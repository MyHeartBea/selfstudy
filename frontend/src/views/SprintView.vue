<script setup>
/**
 * 冲刺计划（维护页）：按考试日倒推每天该清多少题。
 *
 * 数据来自 GET /api/sprint/plan（纯 SQL 统计，零 AI）；口径与今日复习队列
 * 完全一致（新题 = review_count=0 且 next_review_at 为空），页面上的数字要能
 * 和复习页对上。EXAM_DATE 非法或已过考试日时整块降级说明，不瞎算。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import BarRow from '../ui/BarRow.vue'
import GlassCard from '../ui/GlassCard.vue'
import Icon from '../ui/Icon.vue'
import MetricTile from '../ui/MetricTile.vue'
import Skeleton from '../ui/Skeleton.vue'
import StageBadge from '../ui/StageBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'

const plan = ref(null)
const loading = ref(false)
const loadError = ref(false)
const router = useRouter()

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const res = await request.get('/sprint/plan', { silent: true })
    plan.value = res.data.data
  } catch (err) {
    loadError.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)

const daysTone = computed(() => {
  if (!plan.value) return 'accent'
  if (plan.value.days_left <= 7) return 'gold'
  if (plan.value.days_left <= 30) return 'accent'
  return 'teal'
})

function goReview() {
  router.push('/review')
}
</script>

<template>
  <div class="spr">
    <header class="spr-head">
      <div>
        <h1 class="spr-title serif">冲刺计划</h1>
        <p class="spr-sub">按考试日倒推：今天该清多少、每周到哪、哪科最沉。</p>
      </div>
      <UiButton variant="outline" :disabled="loading" @click="load">
        <Icon name="refresh" :size="14" />
        刷新
      </UiButton>
    </header>

    <UiLoadError
      v-if="loadError"
      text="冲刺数据加载失败"
      hint="服务未响应或数据库被占用"
      @retry="load"
    />

    <template v-else-if="loading && !plan">
      <Skeleton variant="rect" :height="120" />
      <Skeleton variant="rect" :height="88" :count="4" />
      <Skeleton variant="rect" :height="220" />
    </template>

    <template v-else-if="plan">
      <UiEmpty
        v-if="plan.date_invalid"
        seal="算"
        text="考试日期没配置好"
        hint="请在 backend/.env 里把 EXAM_DATE 设成合法的 YYYY-MM-DD（当前值无效）"
      />
      <UiEmpty
        v-else-if="plan.passed"
        seal="毕"
        text="考试日已过"
        hint="这条计划是考前冲刺用的；考完了就让它歇着吧"
      />

      <template v-else>
        <GlassCard class="spr-hero">
          <template #badge>
            <StageBadge tone="gold">倒计时</StageBadge>
          </template>
          <div class="spr-hero-in">
            <div class="spr-days" :class="`tone-${daysTone}`">
              <span class="serif spr-days-num">{{ plan.days_left }}</span>
              <span class="spr-days-unit">天</span>
            </div>
            <div class="spr-hero-meta">
              <p class="spr-hero-line">
                距 <b>{{ plan.exam_date }}</b> 初试还有 <b>{{ plan.days_left }}</b> 天
              </p>
              <p class="spr-hero-line dim">
                今天是 {{ plan.today }}，库里在册错题 {{ plan.total_active }} 道
              </p>
              <p class="spr-note">{{ plan.quota_note }}</p>
            </div>
            <div class="spr-hero-cta">
              <UiButton variant="primary" @click="goReview">
                <Icon name="play" :size="14" />
                去复习
              </UiButton>
            </div>
          </div>
        </GlassCard>

        <section class="spr-tiles">
          <MetricTile label="每天目标" :value="plan.daily_target" tone="accent" hint="题 / 天" />
          <MetricTile label="当前积压" :value="plan.due_now" tone="gold" hint="已到期" />
          <MetricTile label="从未复习" :value="plan.never_started" tone="violet" hint="新题" />
          <MetricTile label="今日已复习" :value="plan.reviewed_today" tone="green" hint="题" />
        </section>

        <div class="spr-cols">
          <GlassCard class="spr-card">
            <template #badge>
              <StageBadge tone="accent">科目</StageBadge>
            </template>
            <h2 class="spr-h2 serif">哪科最沉</h2>
            <p v-if="!plan.subjects.length" class="spr-dim">还没有错题，先去录几道。</p>
            <div v-else class="spr-bars">
              <BarRow
                v-for="s in plan.subjects"
                :key="s.name"
                :label="s.name"
                :value="`到期 ${s.due} · 新题 ${s.never}`"
                :percentage="
                  plan.total_active ? Math.round(((s.due + s.never) / plan.total_active) * 100) : 0
                "
              />
            </div>
            <p class="spr-legend">数字 = 该科积压（到期 + 从未复习）占全库比例</p>
          </GlassCard>

          <GlassCard class="spr-card">
            <template #badge>
              <StageBadge tone="teal">里程碑</StageBadge>
            </template>
            <h2 class="spr-h2 serif">按周排的量</h2>
            <ul class="spr-weeks">
              <li v-for="w in plan.weeks" :key="w.label" class="spr-week">
                <span class="spr-week-label">{{ w.label }}</span>
                <span class="spr-week-meta">{{ w.days }} 天 · 到 {{ w.end_date }}</span>
                <span class="spr-week-target">
                  <b class="serif">{{ w.target }}</b> 题
                </span>
              </li>
            </ul>
            <p class="spr-legend">
              每天 {{ plan.daily_target }} 题 × 当周天数；最后不足一周按实际天数算
            </p>
          </GlassCard>
        </div>
      </template>
    </template>
  </div>
</template>

<style scoped>
.spr {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.spr-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}
.spr-title {
  margin: 0;
  font-size: var(--fs-h1);
  font-weight: 900;
  letter-spacing: 0.02em;
}
.spr-sub {
  margin: 6px 0 0;
  color: var(--ink-2);
  font-size: 13.5px;
}
.spr-tiles {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.spr-hero {
  padding: 24px 26px;
}
.spr-hero-in {
  display: flex;
  align-items: center;
  gap: 28px;
}
.spr-days {
  flex: none;
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.spr-days-num {
  font-size: 72px;
  font-weight: 900;
  line-height: 1;
}
.spr-days-unit {
  color: var(--ink-3);
  font-size: 15px;
}
.tone-gold .spr-days-num {
  color: var(--gold);
}
.tone-accent .spr-days-num {
  color: var(--accent);
}
.tone-teal .spr-days-num {
  color: var(--teal);
}
.spr-hero-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.spr-hero-line {
  margin: 0;
  font-size: 15px;
}
.spr-hero-line.dim {
  color: var(--ink-3);
  font-size: 13px;
}
.spr-note {
  margin: 4px 0 0;
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.6;
}
.spr-hero-cta {
  flex: none;
}
.spr-cols {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
  align-items: start;
}
.spr-card {
  padding: 22px 24px 18px;
}
.spr-h2 {
  margin: 4px 0 14px;
  font-size: var(--fs-h2);
  font-weight: 800;
}
.spr-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.spr-dim {
  color: var(--ink-3);
  font-size: 13.5px;
}
.spr-legend {
  margin: 12px 0 0;
  color: var(--ink-3);
  font-size: 12px;
}
.spr-weeks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.spr-week {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 9px 2px;
  border-bottom: 1px dashed var(--glass);
  font-size: 13.5px;
}
.spr-week:last-child {
  border-bottom: none;
}
.spr-week-label {
  font-weight: 700;
}
.spr-week-meta {
  flex: 1;
  color: var(--ink-3);
  font-size: 12.5px;
}
.spr-week-target b {
  font-size: 17px;
  color: var(--accent);
}

@media (max-width: 900px) {
  .spr-tiles {
    grid-template-columns: repeat(2, 1fr);
  }
  .spr-cols {
    grid-template-columns: 1fr;
  }
  .spr-hero-in {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
}
</style>
