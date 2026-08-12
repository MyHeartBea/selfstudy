<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { baseData, loadBaseData, sourceTypes } from '../composables/useBaseData'

const router = useRouter()
const mode = ref('curve')
const count = ref(10)
const filters = reactive({
  subjectId: null,
  subSubjectId: null,
  questionType: '',
  difficulty: null,
  tag: '',
  search: '',
  sourceType: '',
  sourceYear: '',
})

const modes = [
  {
    value: 'curve',
    title: '记忆曲线',
    desc: '到期优先，越久没复习的越靠前',
  },
  {
    value: 'real_exam',
    title: '真题专项',
    desc: '只练真题，按记忆曲线排序',
  },
  {
    value: 'wrong_time',
    title: '按错误时间',
    desc: '最早出错的题最先练',
  },
  {
    value: 'random',
    title: '随机抽题',
    desc: '从所有错题中随机抽取',
  },
]

const subSubjectOptions = computed(() => {
  if (!filters.subjectId) return []
  return baseData.subSubjects.filter((item) => item.subject_id === filters.subjectId)
})

function onSubjectChange() {
  filters.subSubjectId = null
}

function start() {
  const query = {
    mode: mode.value,
    count: count.value,
  }
  if (filters.subjectId) query.subject_id = filters.subjectId
  if (filters.subSubjectId) query.sub_subject_id = filters.subSubjectId
  if (filters.questionType) query.question_type = filters.questionType
  if (filters.difficulty) query.difficulty = filters.difficulty
  if (filters.tag.trim()) query.tag = filters.tag.trim()
  if (filters.search.trim()) query.search = filters.search.trim()
  if (filters.sourceType) query.source_type = filters.sourceType
  if (filters.sourceYear.trim()) query.source_year = filters.sourceYear.trim()
  router.push({ path: '/review', query })
}

onMounted(loadBaseData)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>自主练习</h2>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="section-label">练习方式</div>
      <div class="practice-modes">
        <div
          v-for="m in modes"
          :key="m.value"
          class="practice-mode"
          :class="{ active: mode === m.value }"
          @click="mode = m.value"
        >
          <div class="practice-mode-title">{{ m.title }}</div>
          <div class="practice-mode-desc">{{ m.desc }}</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="filter-card">
      <div class="section-label">抽题数量</div>
      <el-radio-group v-model="count">
        <el-radio-button v-for="n in [10, 20, 50]" :key="n" :value="n">
          {{ n }} 题
        </el-radio-button>
      </el-radio-group>
    </el-card>

    <el-card shadow="never" class="filter-card">
      <div class="section-label">筛选条件</div>
      <el-form :inline="true">
        <el-form-item label="科目">
          <el-select
            v-model="filters.subjectId"
            clearable
            placeholder="全部科目"
            style="width: 170px"
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
        <el-form-item label="二级科目">
          <el-select
            v-model="filters.subSubjectId"
            clearable
            placeholder="全部"
            style="width: 170px"
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
        <el-form-item label="来源分类">
          <el-select
            v-model="filters.sourceType"
            clearable
            placeholder="全部来源"
            style="width: 140px"
          >
            <el-option
              v-for="s in sourceTypes"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="年份">
          <el-input
            v-model="filters.sourceYear"
            clearable
            placeholder="如 2025"
            style="width: 110px"
          />
        </el-form-item>
        <el-form-item label="题型">
          <el-select
            v-model="filters.questionType"
            clearable
            placeholder="全部题型"
            style="width: 130px"
          >
            <el-option label="选择题" value="choice" />
            <el-option label="填空题" value="fill" />
            <el-option label="解答题" value="solution" />
          </el-select>
        </el-form-item>
        <el-form-item label="难度">
          <el-select
            v-model="filters.difficulty"
            clearable
            placeholder="全部难度"
            style="width: 130px"
          >
            <el-option
              v-for="n in [1, 2, 3, 4, 5]"
              :key="n"
              :label="'★'.repeat(n)"
              :value="n"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="知识点">
          <el-input
            v-model="filters.tag"
            clearable
            placeholder="如：微分方程"
            style="width: 150px"
          />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            clearable
            placeholder="搜索题干"
            style="width: 170px"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <div class="practice-start">
      <el-button type="primary" size="large" @click="start">
        开始练习
      </el-button>
    </div>
  </div>
</template>
