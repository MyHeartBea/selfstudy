<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import request from '../api/request'
import MathText from './MathText.vue'
import RichText from './RichText.vue'
import {
  formatTime,
  questionTypeColor,
  questionTypeName,
  subjectColor,
  subjectName,
  subSubjectName,
  sourceTypeColor,
  sourceTypeName,
  truncate,
} from '../composables/useBaseData'

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

const optionList = computed(() => {
  if (!detail.value) return []
  return ['A', 'B', 'C', 'D'].map((key) => ({
    key,
    text: detail.value['option_' + key.toLowerCase()],
  }))
})

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
  loading.value = true
  try {
    const [detailRes, historyRes] = await Promise.all([
      request.get(`/mistakes/${id}`),
      request.get(`/mistakes/${id}/reviews`),
    ])
    const res = detailRes
    detail.value = res.data.data
    reviewHistory.value = historyRes.data.data || []
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
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
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="错题详情" width="760px" top="5vh">
    <div v-loading="loading" class="detail-body">
      <template v-if="detail">
        <div class="detail-meta">
          <el-tag
            :color="questionTypeColor(detail.question_type)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ questionTypeName(detail.question_type) }}
          </el-tag>
          <el-tag
            :color="subjectColor(detail.subject_id)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ subjectName(detail.subject_id) }}
          </el-tag>
          <el-tag v-if="detail.sub_subject_id" type="info" effect="plain">
            {{ subSubjectName(detail.sub_subject_id) }}
          </el-tag>
          <el-tag
            v-if="detail.source_type"
            :color="sourceTypeColor(detail.source_type)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ sourceTypeName(detail.source_type) }}{{ detail.source_year ? ' ' + detail.source_year : '' }}
          </el-tag>
          <el-rate :model-value="detail.difficulty" disabled />
        </div>

        <div class="question-block">
          <MathText :text="detail.question" />
        </div>

        <template v-if="detail.question_type === 'choice'">
          <div
            v-for="opt in optionList"
            :key="opt.key"
            class="option-row"
            :class="{ correct: opt.key === detail.correct_answer }"
          >
            <span class="option-key">{{ opt.key }}</span>
            <MathText :text="opt.text || '（未填写）'" />
            <el-tag v-if="opt.key === detail.correct_answer" type="success" size="small">
              正确答案
            </el-tag>
          </div>
        </template>
        <div v-else class="answer-block">
          <div class="block-label">参考答案</div>
          <MathText :text="detail.correct_answer || '暂无参考答案'" />
          <p
            v-if="detail.answer_aliases && detail.answer_aliases.length"
            class="muted"
            style="margin: 6px 0 0"
          >
            可接受答案：{{ detail.answer_aliases.join('；') }}
          </p>
        </div>

        <div v-if="detail.difficulty_points" class="difficulty-block">
          <div class="block-label">主要难点</div>
          <MathText :text="detail.difficulty_points" />
        </div>

        <div v-if="detail.analysis" class="analysis-block">
          <div class="block-label">解析</div>
          <MathText :text="detail.analysis" />
        </div>

        <div class="info-grid">
          <div><strong>难度：</strong>{{ detail.difficulty }} 星</div>
          <div>
            <strong>解题思路：</strong>
            <MathText v-if="detail.approach" :text="detail.approach" />
            <span v-else>未填写</span>
          </div>
          <div><strong>来源：</strong>{{ detail.source || '未填写' }}</div>
          <div v-if="detail.source_year"><strong>年份：</strong>{{ detail.source_year }}</div>
          <div v-if="detail.source_name"><strong>篇目/卷名：</strong>{{ detail.source_name }}</div>
          <div><strong>创建时间：</strong>{{ formatTime(detail.created_at) }}</div>
        </div>

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
          <el-collapse-item title="知识点补充" name="knowledge">
            <RichText
              v-if="detail.knowledge_extra && detail.knowledge_extra.summary"
              :text="detail.knowledge_extra.summary"
            />
            <p v-else class="muted">暂无补充，可前往知识点库添加。</p>
            <template v-if="detail.related_knowledge && detail.related_knowledge.length">
              <div class="section-label" style="margin-top: 10px">关联知识点</div>
              <div
                v-for="rk in detail.related_knowledge"
                :key="rk.id"
                class="related-kn-card"
                @click="goKnowledge(rk.tag_name)"
              >
                <div class="related-kn-title">
                  {{ rk.tag_name }}
                  <span v-if="rk.subject_name" class="muted">
                    · {{ rk.subject_name }}{{ rk.sub_subject_name ? ' / ' + rk.sub_subject_name : '' }}
                  </span>
                </div>
                <RichText v-if="rk.summary" :text="rk.summary" />
                <p v-else class="muted" style="margin: 4px 0 0">
                  暂无摘要，可前往知识点库补充。
                </p>
              </div>
            </template>
          </el-collapse-item>
          <el-collapse-item
            :title="'同知识点错题（' + detail.related_mistakes.length + '）'"
            name="related"
          >
            <div v-if="detail.related_mistakes.length">
              <div
                v-for="rm in detail.related_mistakes"
                :key="rm.id"
                class="related-card"
                @click="switchDetail(rm.id)"
              >
                <span class="related-question">{{ truncate(rm.question, 40) }}</span>
                <el-tag
                  size="small"
                  :color="subjectColor(rm.subject_id)"
                  effect="dark"
                  style="color: #fff; border-color: transparent"
                >
                  {{ subjectName(rm.subject_id) }}
                </el-tag>
              </div>
            </div>
            <p v-else class="muted">暂无同知识点错题。</p>
          </el-collapse-item>
          <el-collapse-item
            :title="'复习记录（' + reviewHistory.length + '）'"
            name="history"
          >
            <div v-if="reviewHistory.length">
              <div v-for="record in reviewHistory" :key="record.id" class="history-row">
                <el-tag :type="record.result === 'correct' ? 'success' : 'danger'" size="small">
                  {{ record.result === 'correct' ? '记得' : '记错' }}
                </el-tag>
                <span>{{ formatTime(record.reviewed_at) }}</span>
                <span class="history-note">{{ record.note || '无备注' }}</span>
              </div>
            </div>
            <p v-else class="muted">还没有复习记录。</p>
          </el-collapse-item>
        </el-collapse>
      </template>
    </div>
    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="openEdit">编辑</el-button>
      <el-button type="danger" @click="deleteCurrent">删除</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.related-kn-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  margin: 8px 0;
  cursor: pointer;
  background: #f9fafb;
  transition: border-color 0.2s;
}

.related-kn-card:hover {
  border-color: #1f5aa8;
}

.related-kn-title {
  font-weight: 600;
  color: #1d3a5f;
  margin-bottom: 6px;
}
</style>
