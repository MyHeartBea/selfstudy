<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import request from '../api/request'
import {
  subjectColor,
  subjectName,
  subSubjectName,
  truncate,
} from '../composables/useBaseData'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  mistakeId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:modelValue', 'edit', 'deleted'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const loading = ref(false)
const currentId = ref(props.mistakeId)
const detail = ref(null)

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
    const res = await request.get(`/mistakes/${id}`)
    detail.value = res.data.data
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

function openEdit() {
  emit('edit', detail.value)
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
            :color="subjectColor(detail.subject_id)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ subjectName(detail.subject_id) }}
          </el-tag>
          <el-tag v-if="detail.sub_subject_id" type="info" effect="plain">
            {{ subSubjectName(detail.sub_subject_id) }}
          </el-tag>
          <el-rate :model-value="detail.difficulty" disabled />
        </div>

        <div class="question-block">{{ detail.question }}</div>

        <div
          v-for="opt in optionList"
          :key="opt.key"
          class="option-row"
          :class="{ correct: opt.key === detail.correct_answer }"
        >
          <span class="option-key">{{ opt.key }}</span>
          <span>{{ opt.text || '（未填写）' }}</span>
          <el-tag v-if="opt.key === detail.correct_answer" type="success" size="small">
            正确答案
          </el-tag>
        </div>

        <div v-if="detail.analysis" class="analysis-block">
          <div class="block-label">解析</div>
          <p style="margin: 0">{{ detail.analysis }}</p>
        </div>

        <div class="info-grid">
          <div><strong>难度：</strong>{{ detail.difficulty }} 星</div>
          <div><strong>解题思路：</strong>{{ detail.approach || '未填写' }}</div>
          <div><strong>来源：</strong>{{ detail.source || '未填写' }}</div>
          <div><strong>创建时间：</strong>{{ detail.created_at }}</div>
        </div>

        <el-collapse class="detail-collapse">
          <el-collapse-item title="知识点补充" name="knowledge">
            <p
              v-if="detail.knowledge_extra && detail.knowledge_extra.summary"
              style="line-height: 1.7; margin: 6px 0"
            >
              {{ detail.knowledge_extra.summary }}
            </p>
            <p v-else class="muted">暂无补充，可前往知识点库添加。</p>
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
