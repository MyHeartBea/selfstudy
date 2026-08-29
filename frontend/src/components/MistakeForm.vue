<script setup>
/** 错题录入 / 编辑表单（新建与编辑共用，提交 POST /mistakes 或 PUT /mistakes/{id}） */
import { computed, onMounted, reactive, ref, toRef, watch } from 'vue'

import request from '../api/request'
import {
  baseData,
  sourceTypes,
  subjectKind,
  approachPresetsForKind,
  questionTypesForKind,
} from '../composables/useBaseData'
import { createMistakeDraft } from '../composables/mistakeDraft'
import { useSubSubject } from '../composables/useSubSubject'
import { toast } from '../ui/toast'
import UiButton from '../ui/UiButton.vue'
import UiStars from '../ui/UiStars.vue'
import UiSelect from '../ui/UiSelect.vue'
import TagInput from './TagInput.vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  initial: { type: Object, default: null },
  isEdit: { type: Boolean, default: false },
})

const emit = defineEmits(['submitted'])

const submitting = ref(false)
const approachOptions = ref([])
const tagSuggestions = ref([])

function emptyForm() {
  return createMistakeDraft()
}

const form = reactive(emptyForm())

const { subSubjectOptions } = useSubSubject(toRef(form, 'subject_id'))

// —— 科目感知：题型选项与错因快选随科目切换 ——
const currentKind = computed(() => subjectKind(form.subject_id))
const typeOptions = computed(() => questionTypesForKind(currentKind.value))
const approachPresets = computed(() => approachPresetsForKind(currentKind.value))
const isMulti = computed(() => form.question_type === 'multi')
const isEnglishKind = computed(() => currentKind.value === 'english')

// 科目切换后若当前题型不可用则回落到该科目第一项
watch(currentKind, () => {
  if (!typeOptions.value.some((t) => t.value === form.question_type)) {
    form.question_type = typeOptions.value[0].value
  }
})

// 多选题正确答案（存库为排序后的字母串）
const multiAnswer = computed({
  get: () => (form.correct_answer || '').split('').filter((ch) => 'ABCD'.includes(ch)),
  set: (letters) => {
    form.correct_answer = [...letters].sort().join('')
  },
})

function applyApproachPreset(preset) {
  if (!form.approach.includes(preset)) {
    form.approach = form.approach ? `${form.approach}；${preset}` : preset
  }
}

function fillForm(initial) {
  if (!initial) {
    Object.assign(form, emptyForm())
    return
  }
  form.subject_id = initial.subject_id
  form.sub_subject_id = initial.sub_subject_id || null
  form.question_type = initial.question_type || 'choice'
  form.question = initial.question || ''
  form.option_a = initial.option_a || ''
  form.option_b = initial.option_b || ''
  form.option_c = initial.option_c || ''
  form.option_d = initial.option_d || ''
  form.correct_answer = initial.correct_answer || ''
  form.answer_aliases = (initial.answer_aliases || []).slice()
  form.analysis = initial.analysis || ''
  // AI 可能返回小数难度，取整到 1-5
  form.difficulty = Math.min(5, Math.max(1, Math.round(initial.difficulty || 3)))
  form.difficulty_points = initial.difficulty_points || ''
  form.knowledge_tags = (initial.knowledge_tags || []).slice()
  form.approach = initial.approach || ''
  form.source = initial.source || ''
  form.source_type = initial.source_type || 'other'
  form.source_year = initial.source_year || ''
  form.source_name = initial.source_name || ''
  form.images = (initial.images || []).slice()
}

watch(() => props.initial, fillForm, { immediate: true })

function onSubjectChange() {
  form.sub_subject_id = null
}

function onSourceTypeChange() {
  if (form.source_type === 'other') {
    form.source_year = ''
    form.source_name = ''
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
}

// —— 题干图片 ——
function imageSrc(item) {
  // 新上传的是 data URL；已保存的是相对路径 images/xxx
  if (item && item.startsWith('data:')) return item
  const name = item && item.startsWith('images/') ? item.slice('images/'.length) : item
  return '/images/' + name
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

async function onImagePick(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  try {
    const dataUrl = await readFileAsDataUrl(file)
    if (dataUrl.length > 11 * 1024 * 1024) {
      toast.warning('图片过大，请压缩到 8MB 以内再上传')
      return
    }
    form.images.push(dataUrl)
  } catch (err) {
    toast.error(err.message || '图片上传失败')
  }
}

function handleImageRemove(index) {
  form.images.splice(index, 1)
}

function validate() {
  if (!form.subject_id) return '请选择科目'
  if (!form.question.trim()) return '请输入题干'
  if (!form.difficulty) return '请选择难度'
  if (form.question_type === 'choice' && !form.correct_answer) return '选择题请填写正确答案'
  if (form.question_type === 'multi' && !form.correct_answer) return '多选题请勾选正确答案'
  if (form.question_type === 'translation' && !form.correct_answer.trim()) return '翻译请粘贴参考译文，复习时用于对照自评'
  if (form.source_type === 'real_exam' && !form.source_year.trim()) return '真题请填写年份'
  if (form.source_type === 'mock' && (!form.source_year.trim() || !form.source_name.trim())) {
    return '模拟题请填写年份和试卷名称'
  }
  return ''
}

async function submitForm() {
  const error = validate()
  if (error) {
    toast.warning(error)
    return
  }
  submitting.value = true
  const payload = {
    subject_id: form.subject_id,
    sub_subject_id: form.sub_subject_id || null,
    question_type: form.question_type,
    question: form.question,
    option_a: form.option_a,
    option_b: form.option_b,
    option_c: form.option_c,
    option_d: form.option_d,
    correct_answer: form.correct_answer,
    answer_aliases: form.answer_aliases,
    analysis: form.analysis,
    difficulty: form.difficulty,
    difficulty_points: form.difficulty_points,
    knowledge_tags: form.knowledge_tags,
    approach: form.approach,
    source: form.source,
    source_type: form.source_type,
    source_year: form.source_year,
    source_name: form.source_name,
    images: form.images,
  }
  try {
    let res
    if (props.isEdit) {
      res = await request.put(`/mistakes/${props.initial.id}`, payload)
    } else {
      res = await request.post('/mistakes', payload)
    }
    toast.success(props.isEdit ? '修改已保存' : '错题已录入')
    emit('submitted', res.data.data)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function loadApproachOptions() {
  try {
    const [approachRes, tagRes] = await Promise.all([
      request.get('/mistakes/approaches'),
      request.get('/knowledge/tags', { params: { limit: 60 }, silent: true }),
    ])
    approachOptions.value = approachRes.data.data || []
    tagSuggestions.value = (tagRes.data.data || []).map((item) => item.tag)
  } catch (err) {
    approachOptions.value = []
    tagSuggestions.value = []
  }
}

onMounted(loadApproachOptions)
</script>

<template>
  <form class="mform" @submit.prevent="submitForm">
    <div class="field-row">
      <div class="field">
        <label class="field-label">题型</label>
        <div class="seg-row">
          <button
            v-for="t in typeOptions"
            :key="t.value"
            type="button"
            class="seg-btn"
            :class="{ active: form.question_type === t.value }"
            @click="form.question_type = t.value"
          >
            {{ t.label }}
          </button>
        </div>
      </div>
    </div>

    <div class="field-grid">
      <div class="field">
        <label class="field-label required">科目</label>
        <UiSelect
          v-model="form.subject_id"
          :options="baseData.subjects.map((s) => ({ label: s.name, value: s.id }))"
          placeholder="请选择科目"
          @change="onSubjectChange"
        />
      </div>
      <div class="field">
        <label class="field-label">二级科目</label>
        <UiSelect
          v-model="form.sub_subject_id"
          :options="subSubjectOptions.map((s) => ({ label: s.name, value: s.id }))"
          placeholder="选择二级科目"
          clearable
          :disabled="!subSubjectOptions.length"
        />
      </div>
    </div>

    <div class="field">
      <label class="field-label required">题干</label>
      <textarea v-model="form.question" class="field-input" rows="4" placeholder="请输入错题题干"></textarea>
    </div>

    <div class="field">
      <label class="field-label">题干图片</label>
      <div class="question-images">
        <div v-for="(img, index) in form.images" :key="index" class="question-image-item">
          <img :src="imageSrc(img)" alt="题干图片" />
          <button type="button" class="question-image-remove" aria-label="移除图片" @click="handleImageRemove(index)">
            <Icon name="x" :size="12" />
          </button>
        </div>
        <label v-if="form.images.length < 5" class="question-image-add">
          <Icon name="plus-circle" :size="16" />
          添加图片
          <input type="file" accept="image/*" class="visually-hidden" @change="onImagePick" />
        </label>
      </div>
      <p class="field-hint">支持粘贴/上传原题截图（如电路图、拓扑图），最多 5 张</p>
    </div>

    <template v-if="form.question_type === 'choice' || isMulti">
      <div class="field-grid four">
        <div class="field">
          <label class="field-label">选项 A</label>
          <input v-model="form.option_a" class="field-input" placeholder="选项 A 内容" />
        </div>
        <div class="field">
          <label class="field-label">选项 B</label>
          <input v-model="form.option_b" class="field-input" placeholder="选项 B 内容" />
        </div>
        <div class="field">
          <label class="field-label">选项 C</label>
          <input v-model="form.option_c" class="field-input" placeholder="选项 C 内容" />
        </div>
        <div class="field">
          <label class="field-label">选项 D</label>
          <input v-model="form.option_d" class="field-input" placeholder="选项 D 内容" />
        </div>
      </div>

      <div class="field">
        <label class="field-label required">{{ isMulti ? '正确答案（可多选）' : '正确答案' }}</label>
        <div v-if="!isMulti" class="seg-row">
          <button
            v-for="k in ['A', 'B', 'C', 'D']"
            :key="k"
            type="button"
            class="seg-btn"
            :class="{ active: form.correct_answer === k }"
            @click="form.correct_answer = k"
          >
            {{ k }}
          </button>
        </div>
        <div v-else class="seg-row">
          <button
            v-for="k in ['A', 'B', 'C', 'D']"
            :key="k"
            type="button"
            class="seg-btn"
            :class="{ active: multiAnswer.includes(k) }"
            @click="() => { const set = new Set(multiAnswer); set.has(k) ? set.delete(k) : set.add(k); multiAnswer = [...set] }"
          >
            {{ k }}
          </button>
          <span v-if="multiAnswer.length" class="count-tip" style="align-self: center">
            答案：{{ multiAnswer.join('') }}
          </span>
        </div>
      </div>
    </template>

    <div class="field-grid">
      <div class="field">
        <label class="field-label required">难度</label>
        <div class="stars-row">
          <UiStars v-model="form.difficulty" :size="19" />
          <span class="muted" style="font-size: 12px">{{ form.difficulty }} / 5</span>
        </div>
      </div>
      <div class="field">
        <label class="field-label">主要难点</label>
        <input v-model="form.difficulty_points" class="field-input" placeholder="这道题最卡人的地方简析" />
      </div>
    </div>

    <div v-if="form.question_type !== 'choice' && !isMulti" class="field">
      <label class="field-label">{{ form.question_type === 'translation' ? '参考译文' : '参考答案' }}</label>
      <textarea
        v-model="form.correct_answer"
        class="field-input"
        rows="3"
        :placeholder="form.question_type === 'translation' ? '粘贴参考译文，复习时对照自评' : '填空题填写结果，解答题填写答案要点或最终结论'"
      ></textarea>
    </div>

    <div class="field">
      <label class="field-label">解题思路{{ approachPresets.length ? ' / 错因' : '' }}</label>
      <input v-model="form.approach" class="field-input" list="approach-list-v2" placeholder="如：递归、双指针" />
      <datalist id="approach-list-v2">
        <option v-for="a in approachOptions" :key="a" :value="a"></option>
      </datalist>
      <div v-if="approachPresets.length" class="preset-row">
        <button
          v-for="preset in approachPresets"
          :key="preset"
          type="button"
          class="preset-chip"
          @click="applyApproachPreset(preset)"
        >
          {{ preset }}
        </button>
      </div>
    </div>

    <div v-if="form.question_type === 'fill'" class="field">
      <label class="field-label">可接受答案</label>
      <TagInput
        v-model="form.answer_aliases"
        color="var(--green)"
        placeholder="添加等价答案后按回车，如 2-ln2"
      />
    </div>

    <div class="field">
      <label class="field-label">解析</label>
      <textarea v-model="form.analysis" class="field-input" rows="3" placeholder="错因分析、考点讲解"></textarea>
    </div>

    <div class="field">
      <label class="field-label">知识点标签</label>
      <TagInput v-model="form.knowledge_tags" :suggestions="tagSuggestions" placeholder="输入标签后按回车添加" />
    </div>

    <div class="field-grid">
      <div class="field">
        <label class="field-label">题目分类</label>
        <UiSelect
          v-model="form.source_type"
          :options="sourceTypes.map((s) => ({ label: s.label, value: s.value }))"
          @change="onSourceTypeChange"
        />
      </div>
      <div class="field">
        <label class="field-label">来源备注</label>
        <input v-model="form.source" class="field-input" placeholder="如：2025 真题" />
      </div>
    </div>

    <div v-if="form.source_type === 'real_exam' || form.source_type === 'mock'" class="field-grid">
      <div class="field">
        <label class="field-label required">年份</label>
        <input v-model="form.source_year" class="field-input" placeholder="如 2025" />
      </div>
      <div class="field">
        <label class="field-label">篇目/卷名</label>
        <input v-model="form.source_name" placeholder="如 Text 3 / 李林六套卷(一)" class="field-input" />
      </div>
    </div>

    <div class="form-actions">
      <UiButton type="submit" variant="primary" size="lg" :loading="submitting">
        {{ isEdit ? '保存修改' : '提交错题' }}
      </UiButton>
      <UiButton v-if="!isEdit" variant="ghost" size="lg" @click="resetForm">清空</UiButton>
    </div>
  </form>
</template>

<style scoped>
.mform {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field { display: flex; flex-direction: column; gap: 6px; }
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 14px;
}
.field-grid.three { grid-template-columns: repeat(3, 1fr); }
.field-grid.four { grid-template-columns: repeat(4, 1fr); }
@media (max-width: 680px) {
  .field-grid, .field-grid.three, .field-grid.four { grid-template-columns: 1fr; }
}

.field-row { display: flex; }

.field-label {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--ink-2);
}
.required::after {
  content: ' *';
  color: var(--accent);
}

.field-hint { font-size: 12px; color: var(--ink-3); }

.seg-row { display: inline-flex; gap: 6px; flex-wrap: wrap; }
.seg-btn {
  padding: 7px 16px;
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
}
.seg-btn:hover { border-color: var(--accent); color: var(--accent-ink); }
.seg-btn.active {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--surface);
}
[data-theme='dark'] .seg-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.stars-row { display: flex; align-items: center; gap: 10px; height: 36px; }

.preset-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preset-chip {
  padding: 3px 10px;
  border: 1px dashed var(--line-strong);
  border-radius: 999px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.13s;
}
.preset-chip:hover {
  border-color: var(--accent);
  color: var(--accent-ink);
  background: var(--accent-soft);
}

.question-images {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
}
.question-image-item {
  position: relative;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.question-image-item img {
  display: block;
  max-width: 180px;
  max-height: 140px;
  object-fit: contain;
}
.question-image-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
  padding: 0;
}
.question-image-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 1px dashed var(--line-strong);
  border-radius: 9px;
  color: var(--ink-2);
  font-size: 12.5px;
  cursor: pointer;
  transition: all 0.14s;
  align-self: center;
}
.question-image-add:hover { border-color: var(--accent); color: var(--accent-ink); background: var(--accent-soft); }

.form-actions {
  display: flex;
  gap: 10px;
  padding-top: 4px;
}
</style>
