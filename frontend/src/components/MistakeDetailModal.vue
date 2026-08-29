<script setup>
/** 错题详情弹窗：加载详情 + 复习操作 + 暂停/恢复 + 来源修改 + 编辑/删除 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import DetailMeta from './DetailMeta.vue'
import RelatedList from './RelatedList.vue'
import ReviewHistory from './ReviewHistory.vue'
import { formatTime } from '../composables/useBaseData'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiModal from '../ui/UiModal.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'

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
  },
  { immediate: true },
)

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
    emit('deleted', detail.value.id)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}
</script>

<template>
  <UiModal v-model="visible" title="错题详情" size="lg">
    <div v-if="loading" class="detail-loading">
      <span class="skeleton" style="height: 18px; width: 40%"></span>
      <span class="skeleton" style="height: 90px"></span>
      <span class="skeleton" style="height: 60px"></span>
    </div>
    <template v-else-if="detail">
      <DetailMeta :detail="detail" />

      <div class="review-info">
        <div class="review-chips">
          <span class="chip">掌握度 <b>{{ detail.mastery_level || 0 }}</b> 级</span>
          <span class="chip">复习 <b>{{ detail.review_count || 0 }}</b> 次</span>
          <span class="chip">答错 <b>{{ detail.wrong_count || 0 }}</b> 次</span>
          <span class="chip">下次复习：<b>{{ detail.next_review_at ? formatTime(detail.next_review_at) : '尽快' }}</b></span>
          <UiTag
            v-if="detail.last_grade"
            :color="detail.last_grade.verdict === 'correct' ? 'var(--green)' : (detail.last_grade.verdict === 'partial' ? 'var(--gold)' : 'var(--red)')"
            size="sm"
          >
            最近 AI 批改 {{ detail.last_grade.score }} 分
          </UiTag>
        </div>
        <div class="review-actions">
          <UiButton size="sm" variant="success" :loading="reviewing" @click="markReview(true)">标记掌握</UiButton>
          <UiButton size="sm" variant="subtle" :loading="reviewing" @click="markReview(false)">标记生疏</UiButton>
          <UiButton v-if="detail.review_paused" size="sm" variant="subtle" :loading="pausing" @click="resumeReview">恢复复习</UiButton>
          <UiButton v-else size="sm" variant="ghost" :loading="pausing" @click="pauseReview">暂停复习</UiButton>
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

      <RelatedList
        :knowledge-extra="detail.knowledge_extra"
        :related-knowledge="detail.related_knowledge"
        :related-mistakes="detail.related_mistakes"
        @go-knowledge="goKnowledge"
        @switch="switchDetail"
      />
      <div style="margin-top: 10px">
        <details class="history-details">
          <summary>复习记录（{{ reviewHistory.length }}）</summary>
          <ReviewHistory :records="reviewHistory" />
        </details>
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

.review-info {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
  display: flex;
  flex-direction: column;
  gap: 10px;
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
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
}
.chip b { color: var(--ink); }

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
.history-details[open] summary::after { content: '−'; }
.history-details[open] summary { border-radius: var(--r-md) var(--r-md) 0 0; }
</style>
