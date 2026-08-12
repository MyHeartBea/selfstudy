<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import request from '../api/request'
import {
  baseData,
  questionTypeName,
  sourceTypeName,
  sourceTypes,
  subjectName,
  truncate,
} from '../composables/useBaseData'
import MistakeCard from '../components/MistakeCard.vue'
import MistakeDetailDialog from '../components/MistakeDetailDialog.vue'
import MistakeForm from '../components/MistakeForm.vue'

const loading = ref(false)
const router = useRouter()
const items = ref([])
const total = ref(0)
const filters = reactive({
  questionType: '',
  subjectId: null,
  subSubjectId: null,
  sourceType: '',
  sourceYear: '',
  difficulties: [],
  tag: '',
  approach: '',
  search: '',
})
const sortBy = ref('created_desc')
const page = ref(1)
const pageSize = ref(8)

const detailVisible = ref(false)
const detailId = ref(null)
const detailKey = ref(0)
const editVisible = ref(false)
const editTarget = ref(null)
const fileInput = ref(null)
const selectedIds = ref([])
const batchRunning = ref(false)
const importDialogVisible = ref(false)
const pendingImport = ref([])
const importing = ref(false)

const subSubjectOptions = computed(() => {
  if (!filters.subjectId) return []
  return baseData.subSubjects.filter((item) => item.subject_id === filters.subjectId)
})

const activeFilterCount = computed(
  () =>
    [
      filters.questionType,
      filters.subjectId,
      filters.subSubjectId,
      filters.sourceType,
      filters.sourceYear,
      filters.difficulties.length,
      filters.tag,
      filters.approach,
      filters.search,
    ].filter(Boolean).length,
)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function loadMistakes() {
  loading.value = true
  selectedIds.value = []
  try {
    const params = {}
    if (filters.questionType) params.question_type = filters.questionType
    if (filters.subjectId) params.subject_id = filters.subjectId
    if (filters.subSubjectId) params.sub_subject_id = filters.subSubjectId
    if (filters.sourceType) params.source_type = filters.sourceType
    if (filters.sourceYear) params.source_year = filters.sourceYear
    if (filters.difficulties.length) params.difficulty = filters.difficulties
    if (filters.tag) params.tag = filters.tag
    if (filters.approach) params.approach = filters.approach
    if (filters.search) params.search = filters.search
    params.sort = sortBy.value
    params.page = page.value
    params.page_size = pageSize.value
    const res = await request.get('/mistakes', { params })
    const data = res.data.data || {}
    items.value = data.items || []
    total.value = data.total || 0
    if (data.page) page.value = data.page
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function searchMistakes() {
  page.value = 1
  loadMistakes()
}

function resetFilters() {
  filters.questionType = ''
  filters.subjectId = null
  filters.subSubjectId = null
  filters.sourceType = ''
  filters.sourceYear = ''
  filters.difficulties = []
  filters.tag = ''
  filters.approach = ''
  filters.search = ''
  searchMistakes()
}

function onSubjectChange() {
  filters.subSubjectId = null
  searchMistakes()
}

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

async function exportJson() {
  try {
    const params = {}
    if (filters.questionType) params.question_type = filters.questionType
    if (filters.subjectId) params.subject_id = filters.subjectId
    if (filters.subSubjectId) params.sub_subject_id = filters.subSubjectId
    if (filters.sourceType) params.source_type = filters.sourceType
    if (filters.sourceYear) params.source_year = filters.sourceYear
    if (filters.difficulties.length) params.difficulty = filters.difficulties
    if (filters.tag) params.tag = filters.tag
    if (filters.approach) params.approach = filters.approach
    if (filters.search) params.search = filters.search
    params.sort = sortBy.value
    params.page_size = 1000
    const [exportRes, listRes] = await Promise.all([
      request.get('/export'),
      request.get('/mistakes', { params }),
    ])
    const payload = exportRes.data.data
    payload.mistakes = listRes.data.data.items || []
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `考研错题本_${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error('导出失败')
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

function triggerImport() {
  if (fileInput.value) fileInput.value.click()
}

function toggleSelect(id) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
  } else {
    selectedIds.value = [...selectedIds.value, id]
  }
}

async function bulkAction(action, extra = {}) {
  if (!selectedIds.value.length) return
  batchRunning.value = true
  try {
    await request.post('/mistakes/batch', {
      ids: selectedIds.value,
      action,
      ...extra,
    })
    ElMessage.success('批量操作完成')
    selectedIds.value = []
    loadMistakes()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    batchRunning.value = false
  }
}

function bulkPause() {
  bulkAction('pause')
}

function bulkResume() {
  bulkAction('resume')
}

async function bulkSetRealExam() {
  try {
    const promptResult = await ElMessageBox.prompt(
      '请输入真题年份，如 2025',
      '批量设为真题',
      {
        inputPattern: /^(19|20)\d{2}$/,
        inputErrorMessage: '请输入四位数年份，如 2025',
      },
    )
    await bulkAction('source_type', {
      source_type: 'real_exam',
      source_year: String(promptResult.value || '').trim(),
    })
  } catch (err) {
    // 用户取消
  }
}

function bulkSetOther() {
  bulkAction('source_type', { source_type: 'other' })
}

async function bulkDelete() {
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 道错题吗？删除后不可恢复。`,
      '批量删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch (err) {
    return
  }
  bulkAction('delete')
}

async function onImportFile(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file) return
  let parsed
  try {
    parsed = JSON.parse(await file.text())
  } catch (err) {
    ElMessage.error('JSON 文件解析失败')
    return
  }
  const mistakes = Array.isArray(parsed) ? parsed : parsed.mistakes || []
  if (!mistakes.length) {
    ElMessage.warning('文件中没有可导入的错题')
    return
  }
  pendingImport.value = mistakes
  importDialogVisible.value = true
}

async function confirmImport() {
  importing.value = true
  try {
    const res = await request.post('/import', { mistakes: pendingImport.value })
    const result = res.data.data
    ElMessage.success(
      `导入完成：成功 ${result.created} 条${result.failed.length ? `，失败 ${result.failed.length} 条` : ''}`,
    )
    importDialogVisible.value = false
    pendingImport.value = []
    loadMistakes()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    importing.value = false
  }
}

onMounted(loadMistakes)
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
        <el-button @click="triggerImport">
          <el-icon class="btn-icon"><Upload /></el-icon>
          导入 JSON
        </el-button>
        <input
          ref="fileInput"
          type="file"
          accept=".json,application/json"
          style="display: none"
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
          />
        </el-form-item>
        <el-form-item label="思路">
          <el-input
            v-model="filters.approach"
            clearable
            placeholder="如：递归"
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            clearable
            placeholder="搜索题干"
            style="width: 170px"
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
      <el-empty v-if="!items.length" description="暂无错题，去录入一道吧" />
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
        layout="total, prev, pager, next"
        :total="total"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        @current-change="loadMistakes"
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

    <el-dialog v-model="editVisible" title="编辑错题" width="780px" top="4vh">
      <MistakeForm
        v-if="editVisible"
        :initial="editTarget"
        is-edit
        @submitted="onEditSubmitted"
      />
    </el-dialog>
  </div>
</template>
