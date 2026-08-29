<script setup>
/**
 * 错题列表 v2.1：
 * - 勾选框内联到卡片（无浮层遮挡）
 * - 主筛选一行 + 「更多筛选」折叠面板
 * - 筛选条件同步到 URL（刷新/分享不丢）
 * - 批量操作 / 导入导出 / 详情弹窗
 */
import { onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

import {
  baseData,
  questionTypeFilterOptions,
  questionTypeName,
  sourceTypeName,
  sourceTypes,
  subjectName,
  truncate,
} from '../composables/useBaseData'
import { useMistakeFilters } from '../composables/useMistakeFilters'
import { useBulkActions } from '../composables/useBulkActions'
import { useImportExport } from '../composables/useImportExport'
import { useSubSubject } from '../composables/useSubSubject'
import MistakeCard from '../components/MistakeCard.vue'
import MistakeDetailModal from '../components/MistakeDetailModal.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiPagination from '../ui/UiPagination.vue'
import UiModal from '../ui/UiModal.vue'
import UiDropdown from '../ui/UiDropdown.vue'
import Icon from '../ui/Icon.vue'

const router = useRouter()
const route = useRoute()

const selectedIds = ref([])
const showMore = ref(false)

/** 把 URL query 还原为筛选状态（刷新/分享保持筛选）。 */
function readFiltersFromQuery() {
  const q = route.query
  const num = (v) => (v === undefined || v === '' ? null : Number(v))
  return {
    questionType: q.question_type ? String(q.question_type) : '',
    subjectId: q.subject_id ? num(q.subject_id) : null,
    subSubjectId: q.sub_subject_id ? num(q.sub_subject_id) : null,
    sourceType: q.source_type ? String(q.source_type) : '',
    sourceYear: q.source_year ? String(q.source_year) : '',
    difficulties: q.difficulty ? String(q.difficulty).split(',').map(Number).filter(Boolean) : [],
    tag: q.tag ? String(q.tag) : '',
    approach: q.approach ? String(q.approach) : '',
    search: q.search ? String(q.search) : '',
    sort: q.sort ? String(q.sort) : 'created_desc',
    page: q.page ? num(q.page) || 1 : 1,
  }
}

const init = readFiltersFromQuery()

const {
  loading,
  items,
  total,
  filters,
  sortBy,
  page,
  pageSize,
  activeFilterCount,
  totalPages,
  buildParams,
  loadMistakes,
  searchMistakes,
  resetFilters,
  onSubjectChange,
} = useMistakeFilters({
  onBeforeLoad: () => {
    selectedIds.value = []
  },
})

// 用 URL 初始化筛选（必须在首次加载前）
Object.assign(filters, {
  questionType: init.questionType,
  subjectId: init.subjectId,
  subSubjectId: init.subSubjectId,
  sourceType: init.sourceType,
  sourceYear: init.sourceYear,
  difficulties: init.difficulties,
  tag: init.tag,
  approach: init.approach,
  search: init.search,
})
sortBy.value = init.sort
page.value = init.page
if (activeFilterCount.value > 2) showMore.value = true

// 筛选变化 → 同步 URL（replace 不产生历史记录）
let syncTimer = null
watch(
  [filters, sortBy, page],
  () => {
    if (syncTimer) clearTimeout(syncTimer)
    syncTimer = setTimeout(() => {
      const params = buildParams()
      const query = {}
      for (const [key, value] of Object.entries(params)) {
        if (key === 'sort' && value === 'created_desc') continue
        query[key] = Array.isArray(value) ? value.join(',') : String(value)
      }
      if (page.value > 1) query.page = String(page.value)
      router.replace({ query }).catch(() => {})
    }, 350)
  },
  { deep: true },
)

const { subSubjectOptions } = useSubSubject(toRef(filters, 'subjectId'))

const detailVisible = ref(false)
const detailId = ref(null)
const detailKey = ref(0)

const { batchRunning, bulkPause, bulkResume, bulkSetRealExam, bulkSetOther, bulkDelete } =
  useBulkActions({ selectedIds, onDone: loadMistakes })

const {
  importDialogVisible,
  pendingImport,
  importing,
  exportJson,
  onImportFile,
  confirmImport,
} = useImportExport({ buildParams, onImported: loadMistakes })

function openDetail(id) {
  detailId.value = id
  detailKey.value += 1
  detailVisible.value = true
}

function startPractice() {
  router.push('/practice')
}

function startRandom(count) {
  router.push({
    path: '/review',
    query: { mode: 'random', count },
  })
}

function toggleSelect(id, checked) {
  if (checked) {
    if (!selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id]
  } else {
    selectedIds.value = selectedIds.value.filter((v) => v !== id)
  }
}

let searchTimer = null
function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    searchMistakes()
  }, 300)
}

onMounted(loadMistakes)
onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
  if (syncTimer) clearTimeout(syncTimer)
})
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Mistake Library</div>
        <h2>错题列表</h2>
        <p class="view-desc">统一管理、筛选和复习你的考研错题。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="outline" @click="startPractice">
          <Icon name="pencil" :size="15" />
          自主练习
        </UiButton>
        <UiDropdown
          :items="[
            { label: '随机 10 题', command: 10 },
            { label: '随机 20 题', command: 20 },
            { label: '随机 50 题', command: 50 },
          ]"
          @command="startRandom"
        >
          <Icon name="refresh" :size="15" />
          随机抽题
        </UiDropdown>
        <UiButton variant="outline" @click="exportJson">
          <Icon name="download" :size="15" />
          导出
        </UiButton>
        <label class="btn btn-outline btn-md import-label">
          <Icon name="upload" :size="15" />
          导入
          <input
            type="file"
            accept=".json,application/json"
            class="visually-hidden"
            @change="onImportFile"
          />
        </label>
      </div>
    </div>

    <div class="list-toolbar card card-pad">
      <div class="toolbar-row">
        <div class="toolbar-filters">
          <div class="filter-search">
            <Icon name="search" :size="15" class="search-icon" />
            <input
              v-model="filters.search"
              class="field-input"
              placeholder="搜索题干…"
              @input="debouncedSearch"
              @keyup.enter="searchMistakes"
            />
          </div>
          <UiSelect
            v-model="filters.questionType"
            :options="questionTypeFilterOptions"
            placeholder="全部题型"
            clearable
            compact
            @change="searchMistakes"
          />
          <UiSelect
            v-model="filters.subjectId"
            :options="baseData.subjects.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="全部科目"
            clearable
            compact
            @change="onSubjectChange"
          />
          <UiSelect
            v-model="filters.sourceType"
            :options="sourceTypes.map((s) => ({ label: s.label, value: s.value }))"
            placeholder="全部来源"
            clearable
            compact
            @change="searchMistakes"
          />
          <UiSelect
            v-model="sortBy"
            :options="[
              { label: '创建时间倒序', value: 'created_desc' },
              { label: '难度从高到低', value: 'difficulty_desc' },
              { label: '难度从低到高', value: 'difficulty_asc' },
            ]"
            compact
            @change="loadMistakes"
          />
        </div>
        <div class="toolbar-tail">
          <span class="count-tip">共 {{ total }} 条</span>
          <button type="button" class="more-toggle" :class="{ open: showMore }" @click="showMore = !showMore">
            <Icon name="filter" :size="13" />
            更多筛选
            <Icon name="chevron-down" :size="13" class="more-arrow" />
          </button>
        </div>
      </div>

      <Transition name="fold">
        <div v-if="showMore" class="toolbar-more">
          <UiSelect
            v-model="filters.subSubjectId"
            :options="subSubjectOptions.map((s) => ({ label: s.name, value: s.id }))"
            placeholder="二级科目"
            clearable
            compact
            :disabled="!subSubjectOptions.length"
            @change="searchMistakes"
          />
          <input
            v-model="filters.sourceYear"
            class="field-input year-input"
            placeholder="年份 如 2025"
            @keyup.enter="searchMistakes"
            @input="debouncedSearch"
          />
          <div class="diff-chips">
            <button
              v-for="n in [1, 2, 3, 4, 5]"
              :key="n"
              type="button"
              class="diff-chip"
              :class="{ active: filters.difficulties.includes(n) }"
              @click="() => { const idx = filters.difficulties.indexOf(n); idx === -1 ? filters.difficulties.push(n) : filters.difficulties.splice(idx, 1); searchMistakes() }"
            >
              {{ '★'.repeat(n) }}
            </button>
          </div>
          <input
            v-model="filters.tag"
            class="field-input tag-filter"
            placeholder="知识点 如：二叉树遍历"
            @input="debouncedSearch"
          />
          <input
            v-model="filters.approach"
            class="field-input approach-filter"
            placeholder="思路 如：递归"
            @input="debouncedSearch"
          />
          <button type="button" class="link-btn" @click="resetFilters">
            重置全部{{ activeFilterCount ? `（${activeFilterCount} 项）` : '' }}
          </button>
        </div>
      </Transition>
    </div>

    <div v-if="selectedIds.length" class="bulk-bar">
      <span class="bulk-count">已选 {{ selectedIds.length }} 题</span>
      <UiButton size="sm" variant="outline" :loading="batchRunning" @click="bulkPause">暂停</UiButton>
      <UiButton size="sm" variant="outline" :loading="batchRunning" @click="bulkResume">恢复</UiButton>
      <UiButton size="sm" variant="outline" :loading="batchRunning" @click="bulkSetRealExam">设为真题</UiButton>
      <UiButton size="sm" variant="outline" :loading="batchRunning" @click="bulkSetOther">设为自编</UiButton>
      <UiButton size="sm" variant="danger" :loading="batchRunning" @click="bulkDelete">删除</UiButton>
      <UiButton size="sm" variant="ghost" @click="selectedIds = []">清空</UiButton>
    </div>

    <div v-if="loading && !items.length" class="card-grid">
      <div v-for="n in 8" :key="n" class="skeleton" style="height: 210px; border-radius: var(--r-lg)"></div>
    </div>
    <template v-else>
      <div v-if="loadError" class="load-error card card-pad">
        <Icon name="alert" :size="22" />
        <div>
          <div class="load-error-title">错题列表加载失败</div>
          <div class="muted">请检查后端服务是否运行，然后重试。</div>
        </div>
        <UiButton variant="primary" @click="loadMistakes">重新加载</UiButton>
      </div>
      <UiEmpty v-else-if="!items.length" text="暂无错题，去录入一道吧" icon="inbox">
        <UiButton variant="primary" @click="router.push('/capture')">智能录入</UiButton>
      </UiEmpty>
      <div v-else class="card-grid">
        <MistakeCard
          v-for="(item, i) in items"
          :key="item.id"
          :mistake="item"
          :index="total - (page - 1) * pageSize - i"
          :selected="selectedIds.includes(item.id)"
          @open="openDetail"
          @toggle-select="toggleSelect"
        />
      </div>
    </template>

    <div class="pagination-wrap">
      <UiPagination
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        :sizes="[6]"
        @change="loadMistakes"
      />
    </div>

    <MistakeDetailModal
      :key="detailKey"
      v-model="detailVisible"
      :mistake-id="detailId"
      @edit="(m) => router.push(`/mistakes/${m.id}/edit`)"
      @deleted="loadMistakes"
    />

    <UiModal v-model="importDialogVisible" title="导入预览" size="lg">
      <p class="count-tip" style="margin: 0 0 10px">
        共 {{ pendingImport.length }} 条，请确认后导入
      </p>
      <table class="import-table">
        <thead>
          <tr>
            <th>题干</th>
            <th style="width: 110px">科目</th>
            <th style="width: 90px">题型</th>
            <th style="width: 110px">来源</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in pendingImport.slice(0, 20)" :key="i">
            <td>{{ truncate(row.question || '', 60) }}</td>
            <td>{{ subjectName(row.subject_id) }}</td>
            <td>{{ questionTypeName(row.question_type) }}</td>
            <td>{{ sourceTypeName(row.source_type) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="pendingImport.length > 20" class="muted">仅显示前 20 条</p>
      <template #footer>
        <UiButton variant="ghost" @click="importDialogVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="importing" @click="confirmImport">确认导入</UiButton>
      </template>
    </UiModal>
  </div>
</template>

<style scoped>
.import-label { cursor: pointer; }

.list-toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.toolbar-tail {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.filter-search {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 11px;
  color: var(--ink-3);
  pointer-events: none;
}
.filter-search .field-input {
  width: 190px;
  padding-left: 33px;
}

.more-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 11px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.14s;
}
.more-toggle:hover { border-color: var(--accent); color: var(--accent-ink); }
.more-toggle.open { border-color: var(--accent); color: var(--accent-ink); background: var(--accent-soft); }
.more-arrow { transition: transform 0.18s; }
.more-toggle.open .more-arrow { transform: rotate(180deg); }

.toolbar-more {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 12px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
  background: var(--surface-2);
  overflow: hidden;
}
.fold-enter-active, .fold-leave-active {
  transition: all 0.22s cubic-bezier(0.22, 0.8, 0.36, 1);
}
.fold-enter-from, .fold-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.year-input { width: 120px; }
.tag-filter { width: 170px; }
.approach-filter { width: 140px; }

.diff-chips { display: inline-flex; gap: 4px; }
.diff-chip {
  height: 30px;
  padding: 0 9px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--surface);
  color: var(--line-strong);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.13s;
  letter-spacing: 0.05em;
}
.diff-chip:hover { border-color: var(--gold); color: var(--gold); }
.diff-chip.active {
  border-color: var(--gold);
  background: var(--gold-soft);
  color: var(--gold);
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.bulk-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 14px;
  margin-bottom: 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--line));
  background: var(--accent-soft);
  border-radius: var(--r-md);
  animation: bulk-in 0.2s cubic-bezier(0.22, 0.8, 0.36, 1);
}
@keyframes bulk-in {
  from { opacity: 0; transform: translateY(-6px); }
}
.bulk-count {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent-ink);
  margin-right: 4px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.load-error {
  display: flex;
  align-items: center;
  gap: 14px;
  color: var(--red);
}
.load-error-title { font-weight: 700; color: var(--ink); }

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.import-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.import-table th {
  text-align: left;
  padding: 7px 8px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-3);
  font-size: 11.5px;
  letter-spacing: 0.05em;
}
.import-table td {
  padding: 7px 8px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-2);
}
</style>
