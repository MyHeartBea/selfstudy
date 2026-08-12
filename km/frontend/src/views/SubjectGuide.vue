<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import { subjectColor } from '../composables/useBaseData'

const loading = ref(false)
const profiles = ref([])
const subSubjects = ref([])
const editVisible = ref(false)
const tagInput = ref('')
const form = reactive({
  subject_id: null,
  subject_name: '',
  focus_areas: [],
  review_tips: '',
})

async function loadProfiles() {
  loading.value = true
  try {
    const [subjectRes, subSubjectRes] = await Promise.all([
      request.get('/subjects'),
      request.get('/sub_subjects'),
    ])
    const subjects = subjectRes.data.data || []
    subSubjects.value = subSubjectRes.data.data || []
    const items = []
    for (const subject of subjects) {
      try {
        const profileRes = await request.get(`/subjects/${subject.id}/profile`)
        items.push({ ...subject, ...profileRes.data.data })
      } catch (err) {
        items.push({ ...subject, focus_areas: [], review_tips: '' })
      }
    }
    profiles.value = items
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function subSubjectNames(subjectId) {
  const names = subSubjects.value
    .filter((item) => item.subject_id === subjectId)
    .map((item) => item.name)
  return names.join('、') || '—'
}

function openEdit(row) {
  form.subject_id = row.subject_id
  form.subject_name = row.name
  form.focus_areas = (row.focus_areas || []).slice()
  form.review_tips = row.review_tips || ''
  editVisible.value = true
}

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.focus_areas.includes(tag)) {
    form.focus_areas.push(tag)
  }
  tagInput.value = ''
}

function removeTag(tag) {
  form.focus_areas = form.focus_areas.filter((item) => item !== tag)
}

async function save() {
  try {
    await request.put(`/subjects/${form.subject_id}/profile`, {
      focus_areas: form.focus_areas,
      review_tips: form.review_tips,
    })
    ElMessage.success('科目档案已更新')
    editVisible.value = false
    loadProfiles()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(loadProfiles)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="page-header">
      <h2>科目指南</h2>
    </div>

    <el-alert
      title="每个科目的复习重点和表达方式不同：政治重知识点辨析与时政，英语重阅读、词汇、翻译和真题考法，408 四门课要关注跨科目联动。可按自己的情况编辑。"
      type="info"
      :closable="false"
      show-icon
      class="capture-alert"
    />

    <el-card shadow="never">
      <el-table :data="profiles" stripe>
        <el-table-column label="科目" min-width="170">
          <template #default="{ row }">
            <span
              class="subject-name"
              :style="{ color: subjectColor(row.subject_id) }"
            >
              {{ row.name }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="二级科目" min-width="220">
          <template #default="{ row }">
            {{ subSubjectNames(row.subject_id) }}
          </template>
        </el-table-column>
        <el-table-column label="复习重点" min-width="320">
          <template #default="{ row }">
            <el-tag
              v-for="area in row.focus_areas"
              :key="area"
              size="small"
              class="tag-item"
              style="margin: 2px 4px 2px 0"
            >
              {{ area }}
            </el-tag>
            <span v-if="!row.focus_areas || !row.focus_areas.length" class="muted">
              未设置
            </span>
          </template>
        </el-table-column>
        <el-table-column label="方法建议" min-width="360">
          <template #default="{ row }">
            <span class="preserve-text">{{ row.review_tips || '未设置' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="openEdit(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑科目档案" width="640px">
      <el-form label-width="90px">
        <el-form-item label="科目">
          <el-input :model-value="form.subject_name" disabled />
        </el-form-item>
        <el-form-item label="复习重点">
          <div class="tag-editor">
            <el-tag
              v-for="area in form.focus_areas"
              :key="area"
              closable
              class="tag-chip"
              @close="removeTag(area)"
            >
              {{ area }}
            </el-tag>
            <el-input
              v-model="tagInput"
              placeholder="添加重点后按回车"
              size="small"
              style="width: 220px"
              @keyup.enter="addTag"
            />
          </div>
        </el-form-item>
        <el-form-item label="方法建议">
          <el-input
            v-model="form.review_tips"
            type="textarea"
            :rows="6"
            placeholder="写清这个科目的复习方法、常见考法和注意事项"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
