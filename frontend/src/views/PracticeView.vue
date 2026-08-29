<script setup>
/** 自主练习配置：模式选择 + 抽题数量 + 筛选条件 → 跳转 /review */
import { onMounted, reactive, ref, toRef } from 'vue'
import { useRouter } from 'vue-router'

import { baseData, loadBaseData, questionTypeFilterOptions, sourceTypes } from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import Icon from '../ui/Icon.vue'

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
    icon: 'refresh',
  },
  {
    value: 'real_exam',
    title: '真题专项',
    desc: '只练真题，按记忆曲线排序',
    icon: 'target',
  },
  {
    value: 'wrong_time',
    title: '按错误时间',
    desc: '最早出错的题最先练',
    icon: 'clock',
  },
  {
    value: 'random',
    title: '随机抽题',
    desc: '从所有错题中随机抽取',
    icon: 'sparkles',
  },
]

const { subSubjectOptions } = useSubSubject(toRef(filters, 'subjectId'))

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
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Practice Lab</div>
        <h2>自主练习</h2>
        <p class="view-desc">按记忆曲线、错误时间或随机抽题，主动巩固。</p>
      </div>
    </div>

    <div class="card card-pad block">
      <div class="section-label">练习方式</div>
      <div class="practice-modes">
        <button
          v-for="m in modes"
          :key="m.value"
          type="button"
          class="practice-mode"
          :class="{ active: mode === m.value }"
          @click="mode = m.value"
        >
          <Icon :name="m.icon" :size="19" class="mode-icon" />
          <div class="practice-mode-title">{{ m.title }}</div>
          <div class="practice-mode-desc">{{ m.desc }}</div>
        </button>
      </div>
    </div>

    <div class="card card-pad block">
      <div class="section-label">抽题数量</div>
      <div class="count-seg">
        <button
          v-for="n in [10, 20, 50]"
          :key="n"
          type="button"
          class="count-btn"
          :class="{ active: count === n }"
          @click="count = n"
        >
          {{ n }} 题
        </button>
      </div>
    </div>

    <div class="card card-pad block">
      <div class="section-label">筛选条件</div>
      <div class="filter-grid">
        <div class="f-item">
          <label class="f-label">科目</label>
          <UiSelect
            v-model="filters.subjectId"
            :options="baseData.subjects.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="全部科目"
            clearable
            @change="onSubjectChange"
          />
        </div>
        <div class="f-item">
          <label class="f-label">二级科目</label>
          <UiSelect
            v-model="filters.subSubjectId"
            :options="subSubjectOptions.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="全部"
            clearable
            :disabled="!subSubjectOptions.length"
          />
        </div>
        <div class="f-item">
          <label class="f-label">来源分类</label>
          <UiSelect
            v-model="filters.sourceType"
            :options="sourceTypes.map((s) => ({ label: s.label, value: s.value }))"
            placeholder="全部来源"
            clearable
          />
        </div>
        <div class="f-item">
          <label class="f-label">年份</label>
          <input v-model="filters.sourceYear" class="field-input" placeholder="如 2025" />
        </div>
        <div class="f-item">
          <label class="f-label">题型</label>
          <UiSelect
            v-model="filters.questionType"
            :options="questionTypeFilterOptions"
            placeholder="全部题型"
            clearable
          />
        </div>
        <div class="f-item">
          <label class="f-label">难度</label>
          <UiSelect
            v-model="filters.difficulty"
            :options="[1, 2, 3, 4, 5].map((n) => ({ label: '★'.repeat(n), value: n }))"
            placeholder="全部难度"
            clearable
          />
        </div>
        <div class="f-item">
          <label class="f-label">知识点</label>
          <input v-model="filters.tag" class="field-input" placeholder="如：微分方程" />
        </div>
        <div class="f-item">
          <label class="f-label">搜索</label>
          <input v-model="filters.search" class="field-input" placeholder="搜索题干" />
        </div>
      </div>
    </div>

    <div class="practice-start">
      <UiButton variant="primary" size="lg" @click="start">
        <Icon name="play" :size="16" />
        开始练习
      </UiButton>
    </div>
  </div>
</template>

<style scoped>
.block { margin-bottom: 14px; }

.practice-modes {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}
@media (max-width: 860px) { .practice-modes { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .practice-modes { grid-template-columns: 1fr; } }

.practice-mode {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 14px;
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition: all 0.15s;
}
.practice-mode:hover { border-color: var(--accent); }
.practice-mode.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.mode-icon { color: var(--ink-3); margin-bottom: 4px; }
.practice-mode.active .mode-icon { color: var(--accent-ink); }
.practice-mode-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}
.practice-mode-desc {
  font-size: 12px;
  color: var(--ink-3);
}

.count-seg { display: inline-flex; gap: 8px; }
.count-btn {
  height: 38px;
  min-width: 74px;
  padding: 0 16px;
  border: 1.5px solid var(--line-strong);
  border-radius: 11px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.14s;
}
.count-btn:hover { border-color: var(--accent); color: var(--accent-ink); }
.count-btn.active {
  background: var(--ink);
  border-color: var(--ink);
  color: var(--surface);
}
[data-theme='dark'] .count-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px 14px;
}
@media (max-width: 860px) { .filter-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .filter-grid { grid-template-columns: 1fr; } }
.f-item { display: flex; flex-direction: column; gap: 5px; }
.f-label { font-size: 12px; font-weight: 700; color: var(--ink-3); }

.practice-start {
  display: flex;
  justify-content: center;
  padding: 8px 0 24px;
}
</style>
