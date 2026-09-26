<script setup>
/** 错题详情弹窗：加载详情 + 复习操作 + 暂停/恢复 + 来源修改 + 编辑/删除 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import DetailMeta from './DetailMeta.vue'
import EnglishAnalysisPanel from './EnglishAnalysisPanel.vue'
import MathText from './MathText.vue'
import RelatedList from './RelatedList.vue'
import ReviewHistory from './ReviewHistory.vue'
import { formatTime } from '../composables/useBaseData'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiModal from '../ui/UiModal.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import Skeleton from '../ui/Skeleton.vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mistakeId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:modelValue', 'edit', 'deleted'])
const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const loading = ref(false)
const reviewing = ref(false)
const pausing = ref(false)
const sourceUpdating = ref(false)
const currentId = ref(props.mistakeId)
const detail = ref(null)
const reviewHistory = ref([])
// AI 举一反三：variant 为 null 隐藏面板；换题/关弹窗时清掉
const variant = ref(null)
const variantLoading = ref(false)
const variantSaving = ref(false)

let detailRequestId = 0

watch(
  [visible, () => props.mistakeId],
  ([value, id]) => {
    if (id !== undefined && id !== null) {
      currentId.value = id
    }
    if (value && currentId.value) {
      loadDetail(currentId.value)
    }
    // 换题/关闭时清掉上一题的变式，别让张三的变式挂在李四的详情里
    variant.value = null
  },
  { immediate: true },
)

async function genVariant() {
  if (!currentId.value || variantLoading.value) return
  variantLoading.value = true
  try {
    const res = await request.post('/ai/variant', { mistake_id: currentId.value })
    variant.value = res.data.data
  } catch (err) {
    // 拦截器统一弹错（400 未配置 AI / 502 上游失败），这里不用重复提示
  } finally {
    variantLoading.value = false
  }
}

/** 把变式题存成一条新错题（沿用原题的科目/标签，来源记 other）。 */
async function saveVariant() {
  if (!variant.value || !detail.value) return
  variantSaving.value = true
  try {
    await request.post('/mistakes', {
      subject_id: detail.value.subject_id,
      sub_subject_id: detail.value.sub_subject_id || null,
      question_type: detail.value.question_type === 'multi' ? 'choice' : detail.value.question_type,
      question: variant.value.question,
      option_a: variant.value.option_a,
      option_b: variant.value.option_b,
      option_c: variant.value.option_c,
      option_d: variant.value.option_d,
      correct_answer: variant.value.answer,
      analysis: variant.value.analysis,
      difficulty: detail.value.difficulty || 3,
      difficulty_points: variant.value.focus || '变式训练',
      knowledge_tags: detail.value.knowledge_tags || [],
      source_type: 'other',
      source_name: '举一反三',
    })
    toast.success('变式题已存入错题本')
    variant.value = null
  } catch (err) {
    // 校验失败(400)/其它错误拦截器统一提示
  } finally {
    variantSaving.value = false
  }
}

async function loadDetail(id) {
  const requestId = ++detailRequestId
  loading.value = true
  try {
    const [detailRes, historyRes] = await Promise.all([
      request.get(`/mistakes/${id}`),
      request.get(`/mistakes/${id}/reviews`),
    ])
    if (requestId !== detailRequestId) return
    detail.value = detailRes.data.data
    reviewHistory.value = historyRes.data.data || []
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    if (requestId === detailRequestId) loading.value = false
  }
}

function switchDetail(id) {
  currentId.value = id
  loadDetail(id)
}

function goKnowledge(tag) {
  router.push({ path: '/knowledge', query: { tag } })
  visible.value = false
}

function openEdit() {
  emit('edit', detail.value)
}

/** 单题直练：只练这一道（走记忆曲线队列的 id 过滤）。 */
function practiceThis() {
  if (!detail.value) return
  router.push({
    path: '/review',
    query: { mode: 'curve', count: 1, mistake_id: detail.value.id },
  })
  visible.value = false
}

/**
 * 同知识点错题按 detail.knowledge_tags[0] 聚出来（后端 get_mistake_detail 用的就是它），
 * 所以「练这些题」必须带同一个标签，否则按钮下的列表和练到的题不是一批。
 */
const firstTag = computed(() => detail.value?.knowledge_tags?.[0] || '')

function practiceTag(tag) {
  if (!tag) return
  router.push({ path: '/review', query: { mode: 'curve', count: 10, tag } })
  visible.value = false
}

async function markReview(result) {
  if (!detail.value) return
  reviewing.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/review`, { result })
    toast.success(result ? '已标记掌握' : '已标记生疏')
    loadDetail(currentId.value)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    reviewing.value = false
  }
}

async function toggleStar() {
  if (!detail.value) return
  try {
    const res = await request.post(`/mistakes/${detail.value.id}/star`)
    detail.value.starred = !!res.data.data?.starred
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}

async function pauseReview() {
  if (!detail.value) return
  pausing.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/pause`)
    toast.success('已暂停复习，之后不会再推送这道题')
    loadDetail(currentId.value)
  } catch (err) {
  } finally {
    pausing.value = false
  }
}

async function resumeReview() {
  if (!detail.value) return
  pausing.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/resume`)
    toast.success('已恢复复习')
    loadDetail(currentId.value)
  } catch (err) {
  } finally {
    pausing.value = false
  }
}

async function setSourceType(type) {
  if (!detail.value) return
  let year = ''
  if (type === 'real_exam') {
    const result = await confirmDialog({
      title: '设为真题',
      message: '请输入真题年份，如 2025',
      confirmText: '设为真题',
      input: {
        value: detail.value.source_year || '',
        placeholder: '如 2025',
        pattern: /^(19|20)\d{2}$/,
        error: '请输入四位数年份，如 2025',
      },
    })
    if (result === null) return
    year = String(result || '').trim()
  }
  sourceUpdating.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/source-type`, {
      source_type: type,
      source_year: year,
    })
    toast.success('来源分类已更新')
    loadDetail(currentId.value)
  } catch (err) {
  } finally {
    sourceUpdating.value = false
  }
}

async function deleteCurrent() {
  if (!detail.value) {
    toast.warning('详情尚未加载，请稍候再试')
    return
  }
  const ok = await confirmDialog({
    title: '删除确认',
    message: '确定删除这道错题吗？删除后不可恢复。',
    danger: true,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await request.delete(`/mistakes/${detail.value.id}`)
    toast.success('删除成功')
    visible.value = false // 删除成功后关闭详情弹窗
    emit('deleted', detail.value.id)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}
</script>

<template>
  <UiModal v-model="visible" title="错题详情" size="xl">
    <div v-if="loading" class="detail-loading">
      <Skeleton variant="text" :width="'45%'" />
      <Skeleton variant="rect" :height="110" :radius="14" />
      <Skeleton variant="text" :count="2" />
    </div>
    <template v-else-if="detail">
      <!-- 英语整篇：用整篇精读视图（原文逐句对照+各题解析+句型+词汇），不再显示通用框 -->
      <EnglishAnalysisPanel v-if="detail.passage_text" :parsed="detail" readonly />
      <DetailMeta v-else :detail="detail" />

      <div class="review-info">
        <div class="review-chips">
          <span class="chip"
            >掌握度 <b>{{ detail.mastery_level || 0 }}</b> 级</span
          >
          <span class="chip"
            >复习 <b>{{ detail.review_count || 0 }}</b> 次</span
          >
          <span class="chip"
            >答错 <b>{{ detail.wrong_count || 0 }}</b> 次</span
          >
          <span class="chip"
            >下次复习：<b>{{
              detail.next_review_at ? formatTime(detail.next_review_at) : '尽快'
            }}</b></span
          >
          <UiTag
            v-if="detail.last_grade"
            :color="
              detail.last_grade.verdict === 'correct'
                ? 'var(--green)'
                : detail.last_grade.verdict === 'partial'
                  ? 'var(--gold)'
                  : 'var(--red)'
            "
            size="sm"
          >
            最近 AI 批改 {{ detail.last_grade.score }} 分
          </UiTag>
        </div>
        <div class="review-actions">
          <UiButton size="sm" :variant="detail.starred ? 'success' : 'outline'" @click="toggleStar">
            <Icon name="star" :size="13" />
            {{ detail.starred ? '已收藏' : '收藏' }}
          </UiButton>
          <UiButton size="sm" variant="outline" @click="practiceThis">
            <Icon name="play" :size="13" />
            练这道题
          </UiButton>
          <UiButton
            size="sm"
            variant="outline"
            :loading="variantLoading"
            :disabled="Boolean(detail.passage_text)"
            :title="detail.passage_text ? '整篇精读不支持单题变式' : ''"
            @click="genVariant"
          >
            <Icon name="sparkles" :size="13" />
            举一反三
          </UiButton>
          <UiButton size="sm" variant="success" :loading="reviewing" @click="markReview(true)"
            >标记掌握</UiButton
          >
          <UiButton size="sm" variant="subtle" :loading="reviewing" @click="markReview(false)"
            >标记生疏</UiButton
          >
          <UiButton
            v-if="detail.review_paused"
            size="sm"
            variant="subtle"
            :loading="pausing"
            @click="resumeReview"
            >恢复复习</UiButton
          >
          <UiButton v-else size="sm" variant="ghost" :loading="pausing" @click="pauseReview"
            >暂停复习</UiButton
          >
          <UiButton
            v-if="detail.source_type !== 'real_exam'"
            size="sm"
            variant="outline"
            :loading="sourceUpdating"
            @click="setSourceType('real_exam')"
          >
            设为真题
          </UiButton>
        </div>
      </div>

      <!-- AI 举一反三结果：变式题 + 独立答案 + 解析，可一键存入错题本 -->
      <div v-if="variant" class="variant-panel">
        <div class="vp-head">
          <h4 class="vp-title">
            <Icon name="sparkles" :size="14" />
            举一反三 · 变式题
          </h4>
          <span v-if="variant.focus" class="vp-focus">{{ variant.focus }}</span>
        </div>
        <div class="vp-question">
          <MathText :text="variant.question" />
        </div>
        <div v-if="variant.option_a" class="vp-options">
          <div v-for="opt in ['a', 'b', 'c', 'd']" :key="opt" class="vp-option">
            <template v-if="variant[`option_${opt}`]"
              ><b>{{ opt.toUpperCase() }}.</b> <MathText :text="variant[`option_${opt}`]"
            /></template>
          </div>
        </div>
        <div class="vp-answer">
          <span class="vp-label">参考答案</span>
          <MathText :text="variant.answer" />
        </div>
        <div class="vp-analysis">
          <span class="vp-label">解析</span>
          <MathText :text="variant.analysis" />
        </div>
        <div class="vp-actions">
          <UiButton size="sm" variant="primary" :loading="variantSaving" @click="saveVariant">
            存入错题本
          </UiButton>
          <UiButton size="sm" variant="ghost" @click="variant = null">收起</UiButton>
        </div>
      </div>

      <RelatedList
        :knowledge-extra="detail.knowledge_extra"
        :related-knowledge="detail.related_knowledge"
        :related-mistakes="detail.related_mistakes"
        :current-tag="firstTag"
        @go-knowledge="goKnowledge"
        @switch="switchDetail"
        @practice-tag="practiceTag"
      />
      <div style="margin-top: 10px">
        <details class="history-details">
          <summary>复习记录（{{ reviewHistory.length }}）</summary>
          <ReviewHistory :records="reviewHistory" />
        </details>
      </div>

      <!-- 卷宗骑缝章：章盖在卷末（内容流末尾右下），随卷宗滚动，语义正确且免定位纠缠 -->
      <div class="dossier-foot">
        <span class="dossier-seal serif" aria-hidden="true">研</span>
      </div>
    </template>
    <template #footer>
      <UiButton variant="primary" @click="openEdit">编辑</UiButton>
      <UiButton variant="danger" @click="deleteCurrent">删除</UiButton>
      <UiButton variant="ghost" @click="visible = false">关闭</UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.detail-loading {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 卷宗骑缝章：详情 = 一份卷宗，卷末右下盖一方朱砂印 */
.dossier-foot {
  display: flex;
  justify-content: flex-end;
  padding: 8px 6px 2px;
}
.dossier-seal {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: var(--accent-grad);
  color: #fff;
  font-size: 25px;
  font-weight: 900;
  transform: rotate(8deg);
  opacity: 0.88;
  box-shadow:
    0 3px 10px rgba(168, 51, 32, 0.32),
    inset 0 1.5px 0 rgba(255, 255, 255, 0.28);
  pointer-events: none;
  user-select: none;
}

.english-detail {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.ed-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 8px;
}
.ed-title svg {
  color: var(--accent);
}
.ed-passage {
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink);
  margin: 0 0 8px;
}
.ed-trans {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
  margin-bottom: 8px;
  line-height: 1.7;
}
.ed-trans-label {
  flex: none;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--teal);
  background: var(--teal-soft);
  border-radius: 6px;
  padding: 2px 7px;
  align-self: flex-start;
}
.ed-sentences {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}
.ed-sentence {
  border-left: 3px solid var(--accent);
  padding: 4px 10px;
}
.ed-sentence-text {
  font-size: 13px;
  color: var(--ink);
}
.ed-sentence-meta {
  font-size: 11.5px;
  color: var(--ink-3);
  margin-top: 3px;
}
.ed-vocab {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.ed-vocab-label {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--ink-3);
}
.ed-chip {
  font-size: 12px;
  padding: 2px 9px;
  border-radius: 999px;
  border: 1px solid var(--accent);
  color: var(--accent-ink);
  background: var(--accent-soft);
}
.ed-chip.phrase {
  border-color: var(--teal);
  color: var(--teal);
  background: var(--teal-soft);
}

.review-info {
  margin-top: 22px;
  padding: 14px 18px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  background:
    linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(
        135deg,
        color-mix(in srgb, var(--accent) 14%, transparent),
        transparent 50%,
        color-mix(in srgb, var(--teal) 12%, transparent)
      )
      border-box;
  box-shadow: var(--shadow-1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.review-chips {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.chip {
  font-size: 12.5px;
  color: var(--ink-2);
  background: var(--surface-2);
  border: none;
  border-radius: 999px;
  padding: 4px 12px;
}
.chip b {
  color: var(--ink);
  font-family: var(--font-display);
}

.review-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.history-details summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-2);
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.history-details summary::after {
  content: '+';
  font-weight: 400;
  color: var(--ink-3);
}
.history-details[open] summary::after {
  content: '−';
}
.history-details[open] summary {
  border-radius: var(--r-md) var(--r-md) 0 0;
}

/* AI 举一反三面板：与详情其余区块拉开一档 */
.variant-panel {
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px dashed var(--accent-ring);
  border-radius: var(--r-md);
  background: var(--accent-soft);
}
.vp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.vp-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 13.5px;
  color: var(--accent-ink);
}
.vp-focus {
  font-size: 12px;
  color: var(--ink-3);
}
.vp-question {
  font-size: 14.5px;
  line-height: 1.9;
}
.vp-options {
  display: grid;
  gap: 6px;
  margin-top: 10px;
  font-size: 13.5px;
}
.vp-option b {
  margin-right: 6px;
  color: var(--ink-2);
}
.vp-label {
  display: inline-block;
  margin-right: 8px;
  padding: 1px 9px;
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--ink-3);
  font-size: 11.5px;
}
.vp-answer {
  display: flex;
  align-items: baseline;
  margin-top: 12px;
  font-weight: 700;
}
.vp-analysis {
  display: flex;
  align-items: baseline;
  margin-top: 8px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--ink-2);
}
.vp-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
</style>
