<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import request from '../api/request'
import DetailMeta from './DetailMeta.vue'
import RelatedList from './RelatedList.vue'
import ReviewHistory from './ReviewHistory.vue'
import { formatTime } from '../composables/useBaseData'

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
    const res = detailRes
    detail.value = res.data.data
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
}

function openEdit() {
  emit('edit', detail.value)
}

async function markReview(result) {
  if (!detail.value) return
  reviewing.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/review`, { result })
    ElMessage.success(result ? '已标记掌握' : '已标记生疏')
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
    ElMessage.success('已暂停复习，之后不会再推送这道题')
    loadDetail(currentId.value)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    pausing.value = false
  }
}

async function resumeReview() {
  if (!detail.value) return
  pausing.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/resume`)
    ElMessage.success('已恢复复习')
    loadDetail(currentId.value)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    pausing.value = false
  }
}

async function setSourceType(type) {
  if (!detail.value) return
  let year = ''
  if (type === 'real_exam') {
    try {
      const promptResult = await ElMessageBox.prompt(
        '请输入真题年份，如 2025',
        '设为真题',
        {
          inputValue: detail.value.source_year || '',
          inputPattern: /^(19|20)\d{2}$/,
          inputErrorMessage: '请输入四位数年份，如 2025',
        },
      )
      year = String(promptResult.value || '').trim()
    } catch (err) {
      return
    }
  }
  sourceUpdating.value = true
  try {
    await request.post(`/mistakes/${detail.value.id}/source-type`, {
      source_type: type,
      source_year: year,
    })
    ElMessage.success('来源分类已更新')
    loadDetail(currentId.value)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    sourceUpdating.value = false
  }
}

async function deleteCurrent() {
  if (!detail.value) {
    ElMessage.warning("详情尚未加载，请稍候再试")
    return
  }
  try {
    await ElMessageBox.confirm('确定删除这道错题吗？删除后不可恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch (err) {
    return
  }
  try {
    await request.delete(`/mistakes/${detail.value.id}`)
    ElMessage.success('删除成功')
    emit('deleted', detail.value.id)
  } catch (err) {
    // 错误提示由请求拦截器统一处理（拦截器已弹提示，避免重复 toast）
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="错题详情"
    width="760px"
    top="5vh"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" class="detail-body">
      <template v-if="detail">
        <DetailMeta :detail="detail" />

        <div class="review-info">
          <div class="review-info-item">
            <span class="label">掌握度</span>
            <el-rate :model-value="detail.mastery_level || 0" disabled />
          </div>
          <div class="review-info-item">
            <span class="label">复习 {{ detail.review_count || 0 }} 次</span>
          </div>
          <div class="review-info-item">
            <span class="label">答错 {{ detail.wrong_count || 0 }} 次</span>
          </div>
          <div class="review-info-item">
            <span class="label">
              下次复习：{{ detail.next_review_at ? formatTime(detail.next_review_at) : '尽快' }}
            </span>
          </div>
          <div v-if="detail.last_grade" class="review-info-item">
            <span class="label">最近 AI 批改：</span>
            <el-tag
              :type="detail.last_grade.verdict === 'correct' ? 'success' : (detail.last_grade.verdict === 'partial' ? 'warning' : 'danger')"
              size="small"
            >
              {{ detail.last_grade.score }} 分
            </el-tag>
          </div>
          <div class="review-info-actions">
            <el-button
              type="success"
              size="small"
              :loading="reviewing"
              @click="markReview(true)"
            >
              标记掌握
            </el-button>
            <el-button
              type="warning"
              size="small"
              :loading="reviewing"
              @click="markReview(false)"
            >
              标记生疏
            </el-button>
            <el-button
              v-if="detail.review_paused"
              type="info"
              size="small"
              :loading="pausing"
              @click="resumeReview"
            >
              恢复复习
            </el-button>
            <el-button
              v-else
              type="info"
              plain
              size="small"
              :loading="pausing"
              @click="pauseReview"
            >
              暂停复习
            </el-button>
            <el-button
              v-if="detail.source_type !== 'real_exam'"
              type="warning"
              plain
              size="small"
              :loading="sourceUpdating"
              @click="setSourceType('real_exam')"
            >
              设为真题
            </el-button>
          </div>
        </div>

        <el-collapse class="detail-collapse">
          <RelatedList
            :knowledge-extra="detail.knowledge_extra"
            :related-knowledge="detail.related_knowledge"
            :related-mistakes="detail.related_mistakes"
            @go-knowledge="goKnowledge"
            @switch="switchDetail"
          />
          <ReviewHistory :records="reviewHistory" />
        </el-collapse>
      </template>
    </div>
    <template #footer>
      <el-button type="primary" @click="openEdit">编辑</el-button>
      <el-button type="danger" @click="deleteCurrent">删除</el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>
