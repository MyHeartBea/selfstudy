<script setup>
import { onMounted, onUnmounted, ref, toRef } from 'vue'
import { useRouter } from 'vue-router'

import {
  baseData,
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
import MistakeDetailDialog from '../components/MistakeDetailDialog.vue'
import MistakeForm from '../components/MistakeForm.vue'

const router = useRouter()

const selectedIds = ref([])

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

const { subSubjectOptions } = useSubSubject(toRef(filters, 'subjectId'))

const detailVisible = ref(false)
const detailId = ref(null)
const detailKey = ref(0)
const editVisible = ref(false)
const editTarget = ref(null)

const { batchRunning, bulkPause, bulkResume, bulkSetRealExam, bulkSetOther, bulkDelete } =
  useBulkActions({ selectedIds, onDone: loadMistakes })

const {
  fileInput,
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

function openEditFromDetail(mistake) {
  editTarget.value = mistake
  editVisible.value = true
}

function onDetailDeleted() {
  detailVisible.value = false
  loadMistakes()
}

function onEditSubmitted() {
  editVisible.value = false
  loadMistakes()
  if (detailVisible.value) {
    detailKey.value += 1
  }
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

function toggleSelect(id) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
  } else {
    selectedIds.value = [...selectedIds.value, id]
  }
}

function onSizeChange() {
  page.value = 1
  loadMistakes()
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
        <el-button type="primary" plain @click="startPractice">
          <el-icon class="btn-icon"><EditPen /></el-icon>
          自主练习
        </el-button>
        <el-dropdown @command="startRandom">
          <el-button type="primary" plain>
            <el-icon class="btn-icon"><Refresh /></el-icon>
            随机抽题
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="10">随机 10 题</el-dropdown-item>
              <el-dropdown-item command="20">随机 20 题</el-dropdown-item>
              <el-dropdown-item command="50">随机 50 题</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="primary" plain @click="exportJson">
          <el-icon class="btn-icon"><Download /></el-icon>
          导出当前结果
        </el-button>
        <label for="import-file-input" class="el-button">
          <el-icon class="btn-icon"><Upload /></el-icon>
          导入 JSON
        </label>
        <input
          id="import-file-input"
          ref="fileInput"
          type="file"
          accept=".json,application/json"
          class="visually-hidden"
          @change="onImportFile"
        >
      </div>
    </div>

    <div class="hero-metrics" data-reveal>
      <div class="hero-metric">
        <span class="hero-metric-label">错题总数</span>
        <strong>{{ total }}</strong>
      </div>
      <div class="hero-metric">
        <span class="hero-metric-label">筛选条件</span>
        <strong>{{ activeFilterCount }}</strong>
      </div>
      <div class="hero-metric">
        <span class="hero-metric-label">当前页码</span>
        <strong>{{ page }}<small>/{{ totalPages }}</small></strong>
      </div>
    </div>

    <el-card shadow="never" class="filter-card" data-reveal>
      <el-form :inline="true">
        <el-form-item label="题型">
          <el-select
            v-model="filters.questionType"
            clearable
            placeholder="全部题型"
            style="width: 130px"
            @change="searchMistakes"
          >
            <el-option label="选择题" value="choice" />
            <el-option label="填空题" value="fill" />
            <el-option label="解答题" value="solution" />
          </el-select>
        </el-form-item>
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
            @change="searchMistakes"
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
            @keyup.enter="searchMistakes"
          />
        </el-form-item>
        <el-form-item label="难度">
          <el-select
            v-model="filters.difficulties"
            multiple
            collapse-tags
            placeholder="全部难度"
            style="width: 170px"
            @change="searchMistakes"
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
            placeholder="如：二叉树遍历"
            style="width: 150px"
            @input="debouncedSearch"
          />
        </el-form-item>
        <el-form-item label="思路">
          <el-input
            v-model="filters.approach"
            clearable
            placeholder="如：递归"
            style="width: 140px"
            @input="debouncedSearch"
          />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            clearable
            placeholder="搜索题干"
            style="width: 170px"
            @input="debouncedSearch"
            @keyup.enter="searchMistakes"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="searchMistakes">
            搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="sort-row">
        <el-select v-model="sortBy" style="width: 170px" @change="loadMistakes">
          <el-option label="按创建时间倒序" value="created_desc" />
          <el-option label="按难度从高到低" value="difficulty_desc" />
          <el-option label="按难度从低到高" value="difficulty_asc" />
        </el-select>
        <span class="count-tip">共 {{ total }} 条</span>
      </div>
    </el-card>

    <div v-if="selectedIds.length" class="bulk-bar">
      <span class="count-tip">已选 {{ selectedIds.length }} 题</span>
      <el-button size="small" :loading="batchRunning" @click="bulkPause">
        批量暂停
      </el-button>
      <el-button size="small" :loading="batchRunning" @click="bulkResume">
        批量恢复
      </el-button>
      <el-button
        size="small"
        type="warning"
        plain
        :loading="batchRunning"
        @click="bulkSetRealExam"
      >
        批量设为真题
      </el-button>
      <el-button size="small" :loading="batchRunning" @click="bulkSetOther">
        批量设为自编/其他
      </el-button>
      <el-button
        size="small"
        type="danger"
        :loading="batchRunning"
        @click="bulkDelete"
      >
        批量删除
      </el-button>
      <el-button size="small" link @click="selectedIds = []">清空</el-button>
    </div>

    <div v-loading="loading">
      <el-result
        v-if="loadError"
        icon="error"
        title="错题列表加载失败"
        sub-title="请检查后端服务是否运行，然后重试。"
      >
        <template #extra>
          <el-button type="primary" @click="loadMistakes">重新加载</el-button>
        </template>
      </el-result>
      <el-empty v-else-if="!items.length" description="暂无错题，去录入一道吧" />
      <div v-else class="mistake-grid">
        <div v-for="(item, i) in items" :key="item.id" class="mistake-card-wrap">
          <div class="mistake-select-row">
            <el-checkbox
              :model-value="selectedIds.includes(item.id)"
              @change="toggleSelect(item.id)"
            >
              选择
            </el-checkbox>
          </div>
          <MistakeCard
            :mistake="item"
            :index="total - (page - 1) * pageSize - i"
            @open="openDetail"
          />
        </div>
      </div>
    </div>

    <div v-if="total" class="pagination-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :total="total"
        :page-sizes="[8, 20, 50]"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        @current-change="loadMistakes"
        @size-change="onSizeChange"
      />
    </div>

    <MistakeDetailDialog
      :key="detailKey"
      v-model="detailVisible"
      :mistake-id="detailId"
      @edit="openEditFromDetail"
      @deleted="onDetailDeleted"
    />

    <el-dialog
      v-model="importDialogVisible"
      title="导入预览"
      width="860px"
      top="5vh"
      :close-on-click-modal="false"
    >
      <p class="count-tip" style="margin: 0 0 10px">
        共 {{ pendingImport.length }} 条，请确认后导入
      </p>
      <el-table :data="pendingImport.slice(0, 20)" max-height="420" stripe>
        <el-table-column label="题干" min-width="320">
          <template #default="{ row }">
            {{ truncate(row.question || '', 60) }}
          </template>
        </el-table-column>
        <el-table-column label="科目" width="120">
          <template #default="{ row }">
            {{ subjectName(row.subject_id) }}
          </template>
        </el-table-column>
        <el-table-column label="题型" width="100">
          <template #default="{ row }">
            {{ questionTypeName(row.question_type) }}
          </template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            {{ sourceTypeName(row.source_type) }}
          </template>
        </el-table-column>
      </el-table>
      <p v-if="pendingImport.length > 20" class="muted">
        仅显示前 20 条
      </p>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="confirmImport">
          确认导入
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑错题" width="780px" top="4vh" :close-on-click-modal="false">
      <MistakeForm
        v-if="editVisible"
        :initial="editTarget"
        is-edit
        @submitted="onEditSubmitted"
      />
    </el-dialog>
  </div>
</template>
