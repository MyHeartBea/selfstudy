<script setup>
/** 科目指南：各科目复习重点与方法建议，可编辑（PATCH profile） */
import { onMounted, reactive, ref } from 'vue'

import request from '../api/request'
import { subjectColor } from '../composables/useBaseData'
import { toast } from '../ui/toast'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import UiTag from '../ui/UiTag.vue'
import TagInput from '../components/TagInput.vue'
import Icon from '../ui/Icon.vue'

const loading = ref(false)
const saving = ref(false)
const profiles = ref([])
const subSubjects = ref([])
const editVisible = ref(false)
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
    const items = await Promise.all(
      subjects.map(async (subject) => {
        try {
          // silent：profile 404 是预期路径（新库无档案），不触发全局错误 toast
          const profileRes = await request.get(`/subjects/${subject.id}/profile`, {
            silent: true,
          })
          return { ...subject, ...profileRes.data.data }
        } catch (err) {
          return { ...subject, focus_areas: [], review_tips: '' }
        }
      }),
    )
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

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    await request.patch(`/subjects/${form.subject_id}/profile`, {
      focus_areas: form.focus_areas,
      review_tips: form.review_tips,
    })
    toast.success('科目档案已更新')
    editVisible.value = false
    loadProfiles()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    saving.value = false
  }
}

onMounted(loadProfiles)
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Subject Guide</div>
        <h2>科目指南</h2>
        <p class="view-desc">每科复习重点与表达方式，按需编辑维护。</p>
      </div>
    </div>

    <div class="notice card">
      <Icon name="compass" :size="17" class="notice-icon" />
      <p>
        每个科目的复习重点和表达方式不同：政治重知识点辨析与时政，英语重阅读、词汇、翻译和真题考法，
        408 四门课要关注跨科目联动。可按自己的情况编辑。
      </p>
    </div>

    <div v-if="loading && !profiles.length" class="card card-pad">
      <div class="skeleton" style="height: 64px; margin-bottom: 10px"></div>
      <div class="skeleton" style="height: 64px"></div>
    </div>
    <div v-else class="subject-grid">
      <article v-for="row in profiles" :key="row.subject_id" class="card card-pad subject-card">
        <div class="subject-head">
          <span class="subject-dot" :style="{ background: subjectColor(row.subject_id) }"></span>
          <h3 class="subject-name" :style="{ color: subjectColor(row.subject_id) }">{{ row.name }}</h3>
          <UiButton size="sm" variant="outline" @click="openEdit(row)">编辑</UiButton>
        </div>
        <p class="sub-subjects">二级科目：{{ subSubjectNames(row.subject_id) }}</p>

        <div class="section-label" style="margin-top: 14px">复习重点</div>
        <div class="focus-wrap">
          <UiTag v-for="area in row.focus_areas" :key="area" size="sm" style="margin: 0 4px 6px 0">
            {{ area }}
          </UiTag>
          <span v-if="!row.focus_areas || !row.focus_areas.length" class="muted">未设置</span>
        </div>

        <div class="section-label" style="margin-top: 14px">方法建议</div>
        <p class="tips preserve-text">{{ row.review_tips || '未设置' }}</p>
      </article>
    </div>

    <UiModal v-model="editVisible" title="编辑科目档案" size="md">
      <div class="edit-form">
        <div class="field">
          <label class="field-label">科目</label>
          <input :value="form.subject_name" class="field-input" disabled />
        </div>
        <div class="field">
          <label class="field-label">复习重点</label>
          <TagInput v-model="form.focus_areas" placeholder="添加重点后按回车" />
        </div>
        <div class="field">
          <label class="field-label">方法建议</label>
          <textarea
            v-model="form.review_tips"
            class="field-input"
            rows="6"
            placeholder="写清这个科目的复习方法、常见考法和注意事项"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="editVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="saving" @click="save">保存</UiButton>
      </template>
    </UiModal>
  </div>
</template>

<style scoped>
.notice {
  display: flex;
  gap: 11px;
  padding: 13px 16px;
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--ink-2);
  align-items: flex-start;
}
.notice p { margin: 0; line-height: 1.7; }
.notice-icon { color: var(--blue); margin-top: 2px; }

.subject-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
@media (max-width: 860px) { .subject-grid { grid-template-columns: 1fr; } }

.subject-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.subject-dot {
  width: 11px;
  height: 11px;
  border-radius: 4px;
  flex: none;
}
.subject-name {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 700;
  margin-right: auto;
}
.sub-subjects {
  font-size: 12.5px;
  color: var(--ink-3);
  margin-top: 4px;
}
.focus-wrap { display: flex; flex-wrap: wrap; }
.tips {
  font-size: 13px;
  color: var(--ink-2);
  white-space: pre-wrap;
  line-height: 1.7;
}

.edit-form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12.5px; font-weight: 700; color: var(--ink-2); }
</style>
