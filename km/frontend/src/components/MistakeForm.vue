<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import { baseData, sourceTypes } from '../composables/useBaseData'

const props = defineProps({
  initial: { type: Object, default: null },
  isEdit: { type: Boolean, default: false },
})

const emit = defineEmits(['submitted'])

const formRef = ref(null)
const submitting = ref(false)
const tagInput = ref('')
const aliasInput = ref('')
const approachOptions = ref([])

function emptyForm() {
  return {
    subject_id: null,
    sub_subject_id: null,
    question_type: 'choice',
    question: '',
    option_a: '',
    option_b: '',
    option_c: '',
    option_d: '',
    correct_answer: 'A',
    answer_aliases: [],
    analysis: '',
    difficulty: 3,
    difficulty_points: '',
    knowledge_tags: [],
    approach: '',
    source: '',
    source_type: 'other',
    source_year: '',
    source_name: '',
  }
}

const form = reactive(emptyForm())

const rules = {
  subject_id: [{ required: true, message: '请选择科目', trigger: 'change' }],
  question: [{ required: true, message: '请输入题干', trigger: 'blur' }],
  difficulty: [{ required: true, message: '请选择难度', trigger: 'change' }],
}

const subSubjectOptions = computed(() => {
  if (!form.subject_id) return []
  return baseData.subSubjects.filter((item) => item.subject_id === form.subject_id)
})

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
  form.difficulty = initial.difficulty || 3
  form.difficulty_points = initial.difficulty_points || ''
  form.knowledge_tags = (initial.knowledge_tags || []).slice()
  form.approach = initial.approach || ''
  form.source = initial.source || ''
  form.source_type = initial.source_type || 'other'
  form.source_year = initial.source_year || ''
  form.source_name = initial.source_name || ''
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

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.knowledge_tags.includes(tag)) {
    form.knowledge_tags.push(tag)
  }
  tagInput.value = ''
}

function flushTag() {
  if (tagInput.value.trim()) addTag()
}

function removeTag(tag) {
  form.knowledge_tags = form.knowledge_tags.filter((item) => item !== tag)
}

function addAlias() {
  const alias = aliasInput.value.trim()
  if (alias && !form.answer_aliases.includes(alias)) {
    form.answer_aliases.push(alias)
  }
  aliasInput.value = ''
}

function flushAlias() {
  if (aliasInput.value.trim()) addAlias()
}

function removeAlias(alias) {
  form.answer_aliases = form.answer_aliases.filter((item) => item !== alias)
}

function roundDifficulty(value) {
  form.difficulty = Math.round(value || 0)
}

function resetForm() {
  Object.assign(form, emptyForm())
  if (formRef.value) formRef.value.clearValidate()
}

async function submitForm() {
  if (form.question_type === 'choice' && !form.correct_answer) {
    ElMessage.warning('选择题请填写正确答案')
    return
  }
  if (form.source_type === 'real_exam' && !form.source_year.trim()) {
    ElMessage.warning('真题请填写年份')
    return
  }
  if (
    form.source_type === 'mock' &&
    (!form.source_year.trim() || !form.source_name.trim())
  ) {
    ElMessage.warning('模拟题请填写年份和试卷名称')
    return
  }
  if (!form.difficulty_points.trim()) {
    ElMessage.warning('请填写主要难点简析')
    return
  }
  if (!form.analysis.trim()) {
    ElMessage.warning('请填写解析内容')
    return
  }
  try {
    await formRef.value.validate()
  } catch (err) {
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
  }
  try {
    let res
    if (props.isEdit) {
      res = await request.put(`/mistakes/${props.initial.id}`, payload)
    } else {
      res = await request.post('/mistakes', payload)
    }
    ElMessage.success(props.isEdit ? '修改已保存' : '错题已录入')
    emit('submitted', res.data.data)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function loadApproachOptions() {
  try {
    const res = await request.get('/mistakes/approaches')
    approachOptions.value = res.data.data || []
  } catch (err) {
    approachOptions.value = []
  }
}

onMounted(loadApproachOptions)
</script>

<template>
  <div>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="题型" prop="question_type">
        <el-radio-group v-model="form.question_type">
          <el-radio-button value="choice">选择题</el-radio-button>
          <el-radio-button value="fill">填空题</el-radio-button>
          <el-radio-button value="solution">解答题</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="科目" prop="subject_id">
            <el-select
              v-model="form.subject_id"
              placeholder="请选择科目"
              style="width: 100%"
              @change="onSubjectChange"
            >
              <el-option
                v-for="s in baseData.subjects"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="二级科目">
            <el-select
              v-model="form.sub_subject_id"
              placeholder="选择二级科目"
              clearable
              style="width: 100%"
              :disabled="!subSubjectOptions.length"
            >
              <el-option
                v-for="s in subSubjectOptions"
                :key="s.id"
                :label="s.name"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="题干" prop="question">
        <el-input
          v-model="form.question"
          type="textarea"
          :rows="4"
          placeholder="请输入错题题干"
        />
      </el-form-item>

      <el-row v-if="form.question_type === 'choice'" :gutter="16">
        <el-col :span="12">
          <el-form-item label="选项 A">
            <el-input v-model="form.option_a" placeholder="选项 A 内容" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="选项 B">
            <el-input v-model="form.option_b" placeholder="选项 B 内容" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="选项 C">
            <el-input v-model="form.option_c" placeholder="选项 C 内容" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="选项 D">
            <el-input v-model="form.option_d" placeholder="选项 D 内容" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row v-if="form.question_type === 'choice'" :gutter="16">
        <el-col :span="12">
          <el-form-item label="正确答案">
            <el-radio-group v-model="form.correct_answer">
              <el-radio-button v-for="k in ['A', 'B', 'C', 'D']" :key="k" :value="k">
                {{ k }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="难度" prop="difficulty">
            <el-rate
              v-model="form.difficulty"
              :max="5"
              show-score
              clearable
              @change="roundDifficulty"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="主要难点">
            <el-input
              v-model="form.difficulty_points"
              placeholder="这道题最卡人的地方简析"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item v-if="form.question_type !== 'choice'" label="参考答案">
        <el-input
          v-model="form.correct_answer"
          type="textarea"
          :rows="3"
          placeholder="填空题填写结果，解答题填写答案要点或最终结论"
        />
      </el-form-item>

      <el-form-item v-if="form.question_type === 'fill'" label="可接受答案">
        <div class="tag-editor">
          <el-tag
            v-for="alias in form.answer_aliases"
            :key="alias"
            closable
            type="success"
            class="tag-chip"
            @close="removeAlias(alias)"
          >
            {{ alias }}
          </el-tag>
          <el-input
            v-model="aliasInput"
            placeholder="添加等价答案后按回车，如 2-ln2"
            size="small"
            style="width: 260px"
            @keyup.enter="addAlias"
            @blur="flushAlias"
          />
        </div>
      </el-form-item>

      <el-form-item label="解析">
        <el-input
          v-model="form.analysis"
          type="textarea"
          :rows="3"
          placeholder="错因分析、考点讲解"
        />
      </el-form-item>

      <el-form-item label="知识点标签">
        <div class="tag-editor">
          <el-tag
            v-for="t in form.knowledge_tags"
            :key="t"
            closable
            class="tag-chip"
            @close="removeTag(t)"
          >
            {{ t }}
          </el-tag>
          <el-input
            v-model="tagInput"
            placeholder="输入标签后按回车添加"
            size="small"
            style="width: 230px"
            @keyup.enter="addTag"
            @blur="flushTag"
          />
        </div>
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="解题思路">
            <el-input
              v-model="form.approach"
              list="approach-list"
              placeholder="如：递归、双指针"
            />
            <datalist id="approach-list">
              <option v-for="a in approachOptions" :key="a" :value="a" />
            </datalist>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="题目分类">
            <el-select
              v-model="form.source_type"
              style="width: 100%"
              @change="onSourceTypeChange"
            >
              <el-option
                v-for="s in sourceTypes"
                :key="s.value"
                :label="s.label"
                :value="s.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="来源备注">
            <el-input v-model="form.source" placeholder="如：2025 真题" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row
        v-if="form.source_type === 'real_exam' || form.source_type === 'mock'"
        :gutter="16"
      >
        <el-col :span="8">
          <el-form-item label="年份">
            <el-input v-model="form.source_year" placeholder="如 2025" />
          </el-form-item>
        </el-col>
        <el-col
          v-if="form.source_type === 'real_exam' || form.source_type === 'mock'"
          :span="8"
        >
          <el-form-item label="篇目/卷名">
            <el-input
              v-model="form.source_name"
              placeholder="如 Text 3 / 李林六套卷(一)"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ isEdit ? '保存修改' : '提交错题' }}
        </el-button>
        <el-button v-if="!isEdit" @click="resetForm">清空</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>
