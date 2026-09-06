<script setup>
/** 自主练习配置：模式选择 + 抽题数量 + 筛选条件 → 跳转 /review */
import { onMounted, reactive, ref, computed, toRef } from 'vue'
import { useRouter } from 'vue-router'

import { baseData, loadBaseData, questionTypeFilterOptions, sourceTypes } from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import GlassCard from '../ui/GlassCard.vue'
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

const activeMode = computed(() => modes.find((m) => m.value === mode.value) || modes[0])

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

    <!-- 排兵布阵：一卡定出征 -->
    <GlassCard class="deploy" :hover="false">
      <div class="deploy-grid">
        <div class="deploy-left">
          <div class="section-label">练习方式</div>
          <div class="practice-modes">
            <button
              v-for="(m, i) in modes"
              :key="m.value"
              type="button"
              class="practice-mode"
              :class="{ active: mode === m.value }"
              :style="{ '--enter-delay': i * 70 + 'ms' }"
              @click="mode = m.value"
            >
              <span class="mode-icon"><Icon :name="m.icon" :size="19" /></span>
              <span class="mode-check" aria-hidden="true"><Icon name="check" :size="11" /></span>
              <span class="practice-mode-title">{{ m.title }}</span>
              <span class="practice-mode-desc">{{ m.desc }}</span>
            </button>
          </div>
        </div>

        <div class="deploy-right">
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
          <div class="deploy-brief">
            <span class="brief-line"><Icon name="zap" :size="14" />今日出征</span>
            <b class="serif">{{ activeMode.title }} · {{ count }} 题</b>
          </div>
          <UiButton variant="primary" size="lg" block @click="start">
            <Icon name="play" :size="16" />
            开始练习
          </UiButton>
        </div>
      </div>

      <details class="adv-filter">
        <summary>
          <Icon name="filter" :size="13" />
          高级筛选
          <Icon name="chevron-down" :size="13" class="adv-arrow" />
        </summary>
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
      </details>
    </GlassCard>
  </div>
</template>

<style scoped>
/* ---------- 排兵布阵 ---------- */
.deploy { margin-bottom: 14px; }
.deploy-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(250px, 1fr);
  gap: 28px;
}
.deploy-right {
  border-left: 1px dashed var(--line-strong);
  padding-left: 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: stretch;
}
.deploy-brief {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 14px 18px;
  border-radius: var(--r-md);
  background: var(--accent-soft);
  border: 1px solid color-mix(in srgb, var(--accent) 22%, transparent);
}
.brief-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: var(--accent-ink);
}
.deploy-brief b { font-family: var(--font-display); font-size: 19px; font-weight: 900; color: var(--ink); }

/* 高级筛选折叠 */
.adv-filter { margin-top: 24px; border-top: 1px dashed var(--line); padding-top: 14px; }
.adv-filter summary {
  list-style: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-2);
  padding: 5px 12px;
  border-radius: 9px;
  transition: all 0.15s var(--ease);
  user-select: none;
}
.adv-filter summary::-webkit-details-marker { display: none; }
.adv-filter summary:hover { color: var(--accent-ink); background: var(--accent-soft); }
.adv-arrow { transition: transform 0.2s var(--ease); }
.adv-filter[open] .adv-arrow { transform: rotate(180deg); }
.adv-filter .filter-grid { margin-top: 16px; }

.practice-modes {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
@media (max-width: 640px) { .practice-modes { grid-template-columns: 1fr; } }

.practice-mode {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 5px;
  padding: 16px 15px;
  border: 1.5px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition: transform 0.25s var(--spring), border-color 0.18s var(--ease), background 0.18s var(--ease), box-shadow 0.25s var(--ease);
  animation: mode-in 0.5s var(--ease) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes mode-in {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
.practice-mode:hover {
  transform: translateY(-3px);
  border-color: var(--accent);
  box-shadow: var(--shadow-2);
}
.practice-mode.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 0 0 3px var(--accent-ring);
}
.mode-icon {
  width: 42px;
  height: 42px;
  border-radius: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-2);
  color: var(--ink-3);
  margin-bottom: 4px;
  transition: all 0.2s var(--ease);
}
.practice-mode:hover .mode-icon { transform: rotate(-6deg) scale(1.08); }
.practice-mode.active .mode-icon {
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--accent-hover) 40%, transparent);
}
/* 选中印章角标 */
.mode-check {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 22px;
  height: 22px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  background: var(--accent-grad);
  color: #fff;
  transform: rotate(6deg) scale(0);
  transition: transform 0.3s var(--spring);
  box-shadow: 0 2px 8px color-mix(in srgb, var(--accent-hover) 40%, transparent);
}
.practice-mode.active .mode-check { transform: rotate(6deg) scale(1); }
.practice-mode-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}
.practice-mode-desc {
  font-size: 12px;
  color: var(--ink-3);
}

.count-seg {
  display: inline-flex;
  gap: 8px;
  padding: 4px;
  background: var(--surface-2);
  border-radius: 13px;
}
.count-btn {
  height: 40px;
  min-width: 84px;
  padding: 0 18px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ink-3);
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s var(--ease);
}
.count-btn:hover { color: var(--ink); }
.count-btn.active {
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 3px 10px color-mix(in srgb, var(--accent-hover) 40%, transparent);
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

@media (max-width: 900px) {
  .deploy-grid { grid-template-columns: 1fr; gap: 20px; }
  .deploy-right {
    border-left: none;
    padding-left: 0;
    border-top: 1px dashed var(--line-strong);
    padding-top: 20px;
  }
  .deploy-brief { margin-top: 4px; }
}
</style>
