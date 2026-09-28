<script setup>
/** 模考成绩单（自 ReviewView 拆出，StatsView 条带同模式）：总分环 + 统计 + 连考分卷小计 + 错题回顾 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import MathText from '../MathText.vue'
import GlassCard from '../../ui/GlassCard.vue'
import RingProgress from '../../ui/RingProgress.vue'
import StageBadge from '../../ui/StageBadge.vue'
import UiButton from '../../ui/UiButton.vue'

const props = defineProps({
  report: { type: Object, required: true },
})

const router = useRouter()

const details = computed(() => props.report.details || [])
const byPaper = computed(() => props.report.byPaper || [])

function fmtDuration(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
}
</script>

<template>
  <GlassCard class="stage-card km-card mock-report" :hover="false">
    <template #badge><StageBadge text="模考成绩单" /></template>
    <div class="mr-body">
      <RingProgress :percentage="report.score">
        <div class="ring-center-text">
          <b class="num">{{ report.score }} 分</b>
          <span>{{ report.correct }}/{{ report.total }} 正确</span>
        </div>
      </RingProgress>
      <div class="mr-stats">
        <div class="mr-line">
          <span>用时</span><b class="num">{{ fmtDuration(report.usedSec) }}</b>
          <i v-if="report.overtime" class="mr-overtime">超时自动交卷</i>
        </div>
        <div class="mr-line">
          <span>答对</span><b class="num mr-ok">{{ report.correct }}</b>
        </div>
        <div class="mr-line">
          <span>答错</span><b class="num mr-bad">{{ report.total - report.correct }}</b>
        </div>
        <div v-if="report.savedToMistakes" class="mr-line">
          <span>错题入本</span>
          <b class="num">{{ report.savedToMistakes }}</b>
          <i class="mr-overtime saved">已自动收进错题本</i>
        </div>
        <div v-if="byPaper.length" class="mr-papers">
          <div v-for="row in byPaper" :key="row.title" class="mr-paper-row">
            <span class="mr-paper-name">{{ row.title }}</span>
            <span class="num">{{ row.correct }}/{{ row.total }} · {{ row.score }} 分</span>
          </div>
        </div>
        <p class="mr-note">每题结果已计入复习记录（SM-2 自适应调度），错题将按计划再次推送。</p>
      </div>
    </div>
    <div v-if="details.length" class="mr-wrong">
      <div class="block-label">错题回顾</div>
      <div v-for="d in details" :key="d.id" class="mr-item km-item">
        <p class="mr-q"><MathText :text="d.snippet + '…'" /></p>
        <p class="mr-ans">
          你的答案：<b class="mr-bad">{{ d.your }}</b>
          <span class="mr-sep">·</span>
          正确答案：<b class="mr-ok">{{ d.right }}</b>
        </p>
      </div>
    </div>
    <div class="done-actions">
      <UiButton variant="primary" @click="router.push('/practice')">再来一场</UiButton>
      <UiButton variant="ghost" @click="router.push('/mistakes')">返回错题列表</UiButton>
    </div>
  </GlassCard>
</template>

<style scoped>
.stage-card {
  position: relative;
  z-index: 1;
  max-width: 860px;
  margin: 0 auto;
}
.mock-report {
  padding-bottom: 26px;
}
.mr-body {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
  flex-wrap: wrap;
  padding: 8px 0 6px;
}
.mr-stats {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 220px;
}
.mr-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 13.5px;
  color: var(--ink-2);
}
.mr-line b {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 900;
  color: var(--ink);
}
.mr-line span {
  width: 42px;
  flex: none;
  font-size: 12px;
  color: var(--ink-3);
}
.mr-ok {
  color: var(--green);
}
.mr-bad {
  color: var(--red);
}
.mr-overtime {
  font-style: normal;
  font-size: 11.5px;
  color: var(--red);
  background: var(--red-soft);
  padding: 2px 9px;
  border-radius: 999px;
}
.mr-overtime.saved {
  color: var(--green);
  background: var(--green-soft);
}
/* 连考分卷小计 */
.mr-papers {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 6px;
  padding: 8px 12px;
  border-radius: var(--r-sm);
  background: var(--surface-2);
}
.mr-paper-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
  color: var(--ink-2);
}
.mr-paper-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.mr-note {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-3);
}
.mr-wrong {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}
.mr-item {
  padding: 10px 12px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  margin-bottom: 8px;
}
.mr-q {
  margin: 0 0 5px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink);
}
.mr-ans {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-2);
}
.mr-ans b {
  font-weight: 800;
}
.mr-sep {
  margin: 0 6px;
  color: var(--ink-3);
}
.done-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 10px;
  animation: gather-in var(--dur-4) var(--ease-spring) both;
  animation-delay: calc(var(--stagger-2) * 4);
}
@keyframes gather-in {
  from {
    opacity: 0;
    transform: translateY(26px) scale(0.92);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
