<script setup>
/** 自主练习配置：模式选择 + 抽题数量 + 筛选条件 -> 跳转 /review */
import { onMounted, reactive, ref, computed, watch, toRef } from 'vue'
import { useRouter } from 'vue-router'

import {
  baseData,
  loadBaseData,
  questionTypeFilterOptions,
  sourceTypes,
} from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import request from '../api/request'
import { toast } from '../ui/toast'
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
  {
    value: 'mock',
    title: '真题模考',
    desc: '按年份组卷倒计时，交卷统一判分',
    icon: 'calendar',
  },
]

// 模考配置：来源（错题库/真题库）+ 年份（错题库）+ 选题（真题库）+ 时长
// 年份默认留空：当年真题多半还没出，预填当前年只会搜出一张空卷
const mockYear = ref('')
const mockDuration = ref(60)
const mockSource = ref('mistakes') // mistakes | paper
const papers = ref([])
// 多选：勾 1 卷 = 普通整卷模考（paper_id）；勾多卷 = 连考（paper_ids，按卷拼接共用倒计时）
const mockPaperIds = ref([])
const papersLoading = ref(false)

const donePapers = computed(() =>
  papers.value.filter((p) => p.status === 'done' && p.question_count > 0),
)

function togglePaper(id) {
  const idx = mockPaperIds.value.indexOf(id)
  if (idx >= 0) mockPaperIds.value = mockPaperIds.value.filter((x) => x !== id)
  else mockPaperIds.value = [...mockPaperIds.value, id]
}

// 多选小结:共 N 题 + 按客观题节奏的建议时长(约每题 1.5 分钟,向上取整到 5)
const pickedPapers = computed(() =>
  donePapers.value.filter((p) => mockPaperIds.value.includes(p.id)),
)
const pickedTotal = computed(() =>
  pickedPapers.value.reduce((sum, p) => sum + (Number(p.question_count) || 0), 0),
)
const suggestedDuration = computed(() => Math.max(5, Math.ceil((pickedTotal.value * 1.5) / 5) * 5))

async function loadPapers() {
  papersLoading.value = true
  try {
    const res = await request.get('/papers', { params: { status: 'done' }, silent: true })
    papers.value = res.data.data || []
    if (!mockPaperIds.value.length && donePapers.value.length)
      mockPaperIds.value = [donePapers.value[0].id]
  } catch (err) {
    // 静默
  } finally {
    papersLoading.value = false
  }
}

watch(mockSource, (v) => {
  if (v === 'paper' && !papers.value.length) loadPapers()
})

const { subSubjectOptions } = useSubSubject(toRef(filters, 'subjectId'))

const activeMode = computed(() => modes.find((m) => m.value === mode.value) || modes[0])

const mockBriefTail = computed(() => {
  if (mockSource.value === 'paper') {
    const picked = papers.value.filter((p) => mockPaperIds.value.includes(p.id))
    if (picked.length > 1) return `${picked.length} 卷连考 · ${mockDuration.value} 分钟`
    return `${picked[0] ? picked[0].title : '真题卷'} · ${mockDuration.value} 分钟`
  }
  return `${mockYear.value} 年 · ${mockDuration.value} 分钟`
})

function onSubjectChange() {
  filters.subSubjectId = null
}

function start() {
  const query = {
    mode: mode.value,
    count: count.value,
  }
  if (mode.value === 'mock') {
    if (mockSource.value === 'paper') {
      // 真题库整卷模考；勾多卷 = 连考（题目按卷拼接，共用倒计时）
      if (!mockPaperIds.value.length) {
        toast.warning('请至少勾选一份已入库的真题卷（没有就先去「真题库」导入）')
        return
      }
      if (mockPaperIds.value.length === 1) query.paper_id = mockPaperIds.value[0]
      else query.paper_ids = mockPaperIds.value.join(',')
    } else {
      // 错题库真题模考：年份必填
      const year = String(mockYear.value || '').trim()
      if (!/^(19|20)\d{2}$/.test(year)) {
        toast.warning('真题模考请先填写四位年份，如 2021')
        return
      }
      query.source_type = 'real_exam'
      query.source_year = year
    }
    query.duration = mockDuration.value
  }
  if (filters.subjectId) query.subject_id = filters.subjectId
  if (filters.subSubjectId) query.sub_subject_id = filters.subSubjectId
  if (filters.questionType) query.question_type = filters.questionType
  if (filters.difficulty) query.difficulty = filters.difficulty
  if (filters.tag.trim()) query.tag = filters.tag.trim()
  if (filters.search.trim()) query.search = filters.search.trim()
  // 真题模考的来源参数在上面 mock 分支里已经定死，高级筛选不得覆盖
  //（勾过"来源=模拟题"再开真题模考，会把卷子悄悄换成模拟题——实测踩过）
  if (mode.value !== 'mock') {
    if (filters.sourceType) query.source_type = filters.sourceType
    if (filters.sourceYear.trim()) query.source_year = filters.sourceYear.trim()
  }
  router.push({ path: '/review', query })
}

onMounted(loadBaseData)
</script>

<template>
  <div class="page km-editorial">
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
              :style="{ '--enter-delay': `calc(${i} * var(--stagger-2))` }"
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

          <!-- 模考配置：来源 + 年份/选卷 + 时长 -->
          <template v-if="mode === 'mock'">
            <div class="section-label" style="margin-top: 4px">卷面来源</div>
            <div class="src-toggle">
              <button
                type="button"
                :class="{ active: mockSource === 'mistakes' }"
                @click="mockSource = 'mistakes'"
              >
                错题库 · 按年份
              </button>
              <button
                type="button"
                :class="{ active: mockSource === 'paper' }"
                @click="mockSource = 'paper'"
              >
                真题库 · 整卷
              </button>
            </div>

            <template v-if="mockSource === 'mistakes'">
              <div class="section-label" style="margin-top: 4px">模考年份</div>
              <div class="mock-config">
                <input
                  v-model="mockYear"
                  class="field-input year-input"
                  placeholder="如 2021"
                  maxlength="4"
                />
              </div>
            </template>
            <template v-else>
              <div class="section-label" style="margin-top: 4px">
                选择试卷<span class="section-sub">可多选 · 多卷连考</span>
              </div>
              <div class="mock-config">
                <div v-if="papersLoading" class="cap">正在读取卷库…</div>
                <div v-else-if="!donePapers.length" class="cap">卷库还没有可用试卷</div>
                <div v-else class="paper-pick" role="group" aria-label="选择试卷（可多选连考）">
                  <button
                    v-for="p in donePapers"
                    :key="p.id"
                    type="button"
                    class="paper-chip km-item clickable"
                    :class="{ active: mockPaperIds.includes(p.id) }"
                    :aria-pressed="mockPaperIds.includes(p.id)"
                    @click="togglePaper(p.id)"
                  >
                    <span class="chip-check" aria-hidden="true"
                      ><Icon name="check" :size="11"
                    /></span>
                    <span class="paper-chip-title">{{ p.title }}</span>
                    <span class="paper-chip-count num">{{ p.question_count }} 题</span>
                  </button>
                </div>
                <p v-if="mockPaperIds.length > 1" class="cap">
                  连考：{{ mockPaperIds.length }} 卷按顺序拼成一张卷面，共用同一个倒计时。
                </p>
                <p v-if="mockPaperIds.length" class="cap">
                  已选共 <b class="num">{{ pickedTotal }}</b> 题 —— 建议时长约
                  <b class="num">{{ suggestedDuration }}</b> 分钟（每题 1.5 分钟估算）
                </p>
                <p class="cap">
                  真题库只有 {{ donePapers.length }} 份可用卷——
                  <router-link to="/papers" class="mock-link">去真题库导入更多</router-link>
                </p>
              </div>
            </template>

            <div class="section-label" style="margin-top: 6px">考试时长</div>
            <div class="count-seg">
              <button
                v-for="m in [30, 60, 90, 120, 180]"
                :key="m"
                type="button"
                class="count-btn"
                :class="{ active: mockDuration === m }"
                @click="mockDuration = m"
              >
                {{ m }} 分
              </button>
            </div>
          </template>

          <div class="deploy-brief">
            <span class="brief-line"><Icon name="zap" :size="14" />今日出征</span>
            <b class="serif">
              {{ activeMode.title }} · {{ count }} 题<template v-if="mode === 'mock'">
                · {{ mockBriefTail }}</template
              >
            </b>
          </div>
          <UiButton variant="primary" size="lg" block @click="start">
            <Icon name="play" :size="16" />
            开始练习
          </UiButton>
        </div>
      </div>
    </GlassCard>

    <!-- 高级筛选放在玻璃卡之外：gcard-body 的 overflow:hidden（流光裁切用）
         会把 UiSelect 的下拉菜单整个裁掉（实测科目下拉显示不全）。
         普通 .card 没有 overflow 裁切，下拉可自由溢出。 -->
    <details class="adv-filter card card-pad">
      <summary>
        <Icon name="filter" :size="13" />
        高级筛选
        <Icon name="chevron-down" :size="13" class="adv-arrow" />
      </summary>
      <div class="filter-grid">
        <div class="f-item km-item">
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
            :options="[1, 2, 3, 4, 5].map((n) => ({ label: `${n} 星`, value: n }))"
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
  </div>
</template>

<style scoped>
/* ---------- 排兵布阵 ---------- */
.deploy {
  margin-bottom: 14px;
}
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
.deploy-brief b {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 900;
  color: var(--ink);
}

/* 高级筛选折叠（已迁出玻璃卡，自成一张纸片卡；下拉不再被 overflow 裁切） */
.adv-filter {
  margin-top: 16px;
  cursor: default;
}
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
  margin-left: -12px;
  border-radius: 9px;
  transition: all 0.15s var(--ease);
  user-select: none;
}
.adv-filter summary::-webkit-details-marker {
  display: none;
}
.adv-filter summary:hover {
  color: var(--accent-ink);
  background: var(--accent-soft);
}
.adv-arrow {
  transition: transform 0.2s var(--ease);
}
.adv-filter[open] .adv-arrow {
  transform: rotate(180deg);
}
.adv-filter .filter-grid {
  margin-top: 16px;
}

.practice-modes {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
@media (max-width: 640px) {
  .practice-modes {
    grid-template-columns: 1fr;
  }
}

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
  transition:
    transform 0.25s var(--spring),
    border-color 0.18s var(--ease),
    background 0.18s var(--ease),
    box-shadow 0.25s var(--ease);
  animation: mode-in var(--dur-4) var(--ease-enter) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes mode-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
.practice-mode:hover .mode-icon {
  transform: rotate(-6deg) scale(1.08);
}
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
.practice-mode.active .mode-check {
  transform: rotate(6deg) scale(1);
}
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
.count-btn:hover {
  color: var(--ink);
}
.count-btn.active {
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 3px 10px color-mix(in srgb, var(--accent-hover) 40%, transparent);
}

/* 模考配置 */
.mock-config {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}
.mock-config .year-input {
  width: 130px;
}
.mock-config .count-seg {
  flex-wrap: wrap;
}
.mock-config .mock-link {
  color: var(--accent-ink);
  font-weight: 700;
  text-decoration: underline;
}
.src-toggle {
  display: inline-flex;
  gap: 3px;
  padding: 3px;
  background: var(--surface-2);
  border-radius: 999px;
}
.src-toggle button {
  border: none;
  background: transparent;
  color: var(--ink-3);
  font-size: 12.5px;
  font-weight: 600;
  padding: 5px 15px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.src-toggle button:hover {
  color: var(--ink);
}
.src-toggle button.active {
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--accent-hover) 40%, transparent);
}

/* 多选卷子（1 卷 = 整卷模考，多卷 = 连考） */
.paper-pick {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}
.paper-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  max-width: 100%;
  padding: 7px 12px;
  border: 1px solid var(--surface-glass);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.paper-chip:hover {
  color: var(--ink);
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
}
.paper-chip.active {
  background: color-mix(in srgb, var(--accent) 10%, var(--surface-2));
  border-color: color-mix(in srgb, var(--accent) 45%, transparent);
  color: var(--ink);
}
.chip-check {
  flex: none;
  width: 16px;
  height: 16px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  background: transparent;
  border: 1.5px solid var(--ink-3);
  color: transparent;
  transition: all 0.18s var(--ease);
}
.paper-chip.active .chip-check {
  background: var(--accent-grad);
  border-color: transparent;
  color: #fff;
}
.paper-chip-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.paper-chip-count {
  flex: none;
  font-size: 11px;
  color: var(--ink-3);
}
.section-sub {
  margin-left: 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-3);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px 14px;
}
@media (max-width: 860px) {
  .filter-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 480px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
.f-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.f-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-3);
}

@media (max-width: 900px) {
  .deploy-grid {
    grid-template-columns: 1fr;
    gap: 20px;
  }
  .deploy-right {
    border-left: none;
    padding-left: 0;
    border-top: 1px dashed var(--line-strong);
    padding-top: 20px;
  }
  .deploy-brief {
    margin-top: 4px;
  }
}
</style>
