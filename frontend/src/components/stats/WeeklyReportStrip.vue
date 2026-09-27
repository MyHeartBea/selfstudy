<script setup>
/**
 * AI 错因周报条（[04]）：近 7 天错因聚类 + 训练建议。
 * 自取数（POST /ai/weekly-report，按天缓存，重新生成带 force=1）；
 * 报告里的知识点标签点击后 emit 给父组件走统一的练习跳转。
 */
import { ref } from 'vue'

import request from '../../api/request'
import MathText from '../MathText.vue'
import GlassCard from '../../ui/GlassCard.vue'
import Icon from '../../ui/Icon.vue'
import UiButton from '../../ui/UiButton.vue'
import UiTag from '../../ui/UiTag.vue'

const emit = defineEmits(['practice'])

const report = ref(null)
const reportLoading = ref(false)

async function loadWeeklyReport(force = false) {
  if (reportLoading.value) return
  reportLoading.value = true
  try {
    const res = await request.post(`/ai/weekly-report${force ? '?force=1' : ''}`, {})
    report.value = res.data.data
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    reportLoading.value = false
  }
}
</script>

<template>
  <GlassCard class="span3 report-strip km-live" :hover="false">
    <!-- 复合悬停装饰层 -->
    <span class="km-live__ghost" aria-hidden="true">08</span>
    <span class="km-live__rule" aria-hidden="true"></span>
    <span class="km-live__corner tl" aria-hidden="true"></span>
    <span class="km-live__corner tr" aria-hidden="true"></span>
    <span class="km-live__corner bl" aria-hidden="true"></span>
    <span class="km-live__corner br" aria-hidden="true"></span>
    <span class="km-live__scan" aria-hidden="true"></span>
    <div class="rp-head">
      <div>
        <h3 class="panel-title" data-reveal-lines>AI 错因周报</h3>
        <p class="cap">近 7 天答错题目按错因聚类，给出针对性训练建议</p>
      </div>
      <div class="rp-actions">
        <span v-if="report && !report.empty && report.cached" class="rp-cached"
          >今日已生成 · 缓存</span
        >
        <UiButton
          variant="primary"
          size="sm"
          :loading="reportLoading"
          @click="loadWeeklyReport(!report || report.cached)"
        >
          <Icon name="sparkles" :size="14" />
          {{ report ? '重新生成' : '生成本周报告' }}
        </UiButton>
      </div>
    </div>
    <p v-if="reportLoading" class="rp-hint">AI 正在聚类分析近 7 天的错题…（约 10-30 秒）</p>
    <p v-else-if="report?.empty" class="rp-hint">{{ report.message }}</p>
    <template v-else-if="report">
      <p class="rp-summary"><MathText :text="report.summary" /></p>
      <div class="rp-clusters">
        <div v-for="(c, i) in report.clusters" :key="i" class="rp-cluster">
          <span class="rp-rank num km-num">{{ i + 1 }}</span>
          <div class="rp-body">
            <div class="rp-line">
              <b class="serif">{{ c.cause }}</b>
              <span class="rp-count num km-num">{{ c.count }} 题</span>
            </div>
            <p class="rp-advice"><MathText :text="c.advice" /></p>
            <div v-if="c.tags && c.tags.length" class="rp-tags">
              <UiTag
                v-for="t in c.tags"
                :key="t"
                size="sm"
                color="var(--gold)"
                soft
                clickable
                @click="emit('practice', t)"
                >{{ t }}</UiTag
              >
            </div>
          </div>
        </div>
      </div>
    </template>
  </GlassCard>
</template>

<style scoped>
/* 条带头部（原主文件共享规则中 rp-head 的部分） */
.stats-page .rp-head {
  align-items: baseline;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(20px, 3vh, 36px);
}
.stats-page .rp-head .panel-title {
  font-size: 11.5px !important;
  letter-spacing: 0.2em !important;
  text-transform: uppercase !important;
  color: var(--ink-2) !important;
}
.stats-page .rp-head::before {
  content: '[04]';
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin-right: 2px;
}
/* 报告读数与提示沿用主文件的极小等宽排印 */
.stats-page :is(.rp-cluster b) {
  font-size: clamp(1.7rem, 2.9vw, 2.6rem) !important;
  line-height: 1 !important;
  letter-spacing: -0.03em !important;
}
.stats-page .rp-hint {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ink-3);
}

/* 报告本体 */
.rp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.rp-hint {
  margin: 14px 0 2px;
  font-size: 13px;
  color: var(--ink-3);
}
.rp-summary {
  margin: 14px 0 2px;
  padding: 12px 16px;
  border-radius: var(--r-md);
  background: var(--accent-soft);
  font-size: 14px;
  line-height: 1.9;
  color: var(--ink);
}
.rp-clusters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.rp-cluster {
  display: flex;
  gap: 11px;
  padding: 12px 14px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
}
.rp-rank {
  width: 24px;
  height: 24px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 800;
  font-size: 12px;
}
.rp-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.rp-line b {
  font-size: 15px;
  color: var(--ink);
}
.rp-count {
  font-size: 12px;
  color: var(--accent-ink);
  font-weight: 700;
}
.rp-advice {
  margin: 4px 0 6px;
  font-size: 12.8px;
  line-height: 1.8;
  color: var(--ink-2);
}
.rp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.rp-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.rp-cached {
  font-size: 12px;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 3px 11px;
  border-radius: 999px;
}
</style>
