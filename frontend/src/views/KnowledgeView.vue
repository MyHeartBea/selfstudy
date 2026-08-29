<script setup>
/** 知识点库：筛选 + 分页表格 + 编辑/创建弹窗 + AI 总结 + 一键练习 */
import { onMounted, reactive, ref, toRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import {
  baseData,
  formatTime,
  subjectName,
  subSubjectName,
} from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import KnowledgeEditModal from '../components/KnowledgeEditModal.vue'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiPagination from '../ui/UiPagination.vue'
import Icon from '../ui/Icon.vue'

const loading = ref(false)
const router = useRouter()
const route = useRoute()
const items = ref([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const filters = reactive({
  subjectId: null,
  subSubjectId: null,
  tag: '',
})
const editVisible = ref(false)
const createVisible = ref(false)
const editing = ref(null)
const summarizingId = ref(null)

const { subSubjectOptions } = useSubSubject(toRef(filters, 'subjectId'))

async function loadKnowledge() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filters.subjectId) params.subject_id = filters.subjectId
    if (filters.subSubjectId) params.sub_subject_id = filters.subSubjectId
    if (filters.tag) params.tag = filters.tag
    const res = await request.get('/knowledge', { params })
    const data = res.data.data
    if (Array.isArray(data)) {
      items.value = data
      total.value = data.length
    } else {
      items.value = data?.items || []
      total.value = data?.total || 0
    }
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function searchKnowledge() {
  page.value = 1
  loadKnowledge()
}

function resetFilters() {
  filters.subjectId = null
  filters.subSubjectId = null
  filters.tag = ''
  searchKnowledge()
}

function practiceTag(tag) {
  router.push({
    path: '/review',
    query: { mode: 'curve', count: 10, tag },
  })
}

function onSubjectChange() {
  filters.subSubjectId = null
  searchKnowledge()
}

function openEdit(row) {
  editing.value = row
  createVisible.value = false
  editVisible.value = true
}

function openCreate() {
  editing.value = null
  editVisible.value = false
  createVisible.value = true
}

function onSaved() {
  editVisible.value = false
  createVisible.value = false
  loadKnowledge()
}

async function autoSummarize(row) {
  summarizingId.value = row.id
  try {
    await request.post(`/knowledge/${row.id}/auto-summarize`)
    toast.success('总结已生成')
    loadKnowledge()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    summarizingId.value = null
  }
}

async function remove(row) {
  const ok = await confirmDialog({
    title: '删除确认',
    message: `确定删除知识点“${row.tag_name}”吗？不影响已关联错题。`,
    danger: true,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await request.delete(`/knowledge/${row.id}`)
    toast.success('删除成功')
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    loadKnowledge()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(() => {
  const queryTag = route.query.tag
  if (queryTag) {
    filters.tag = String(queryTag)
  }
  loadKnowledge()
})
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Knowledge Base</div>
        <h2>知识点库</h2>
        <p class="view-desc">沉淀每个标签背后的核心概念与补充讲解。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="primary" @click="openCreate">
          <Icon name="plus-circle" :size="15" />
          添加知识点
        </UiButton>
      </div>
    </div>

    <div class="card card-pad filter-bar">
      <UiSelect
        v-model="filters.subjectId"
        :options="baseData.subjects.map((s) => ({ label: s.name, value: s.id }))"
        placeholder="全部科目"
        clearable
        compact
        @change="onSubjectChange"
      />
      <UiSelect
        v-model="filters.subSubjectId"
        :options="subSubjectOptions.map((s) => ({ label: s.name, value: s.id }))"
        placeholder="二级科目"
        clearable
        compact
        :disabled="!subSubjectOptions.length"
        @change="searchKnowledge"
      />
      <input
        v-model="filters.tag"
        class="field-input tag-input"
        placeholder="搜索知识点标签"
        @keyup.enter="searchKnowledge"
      />
      <UiButton variant="primary" :loading="loading" @click="searchKnowledge">搜索</UiButton>
      <UiButton variant="ghost" @click="resetFilters">重置</UiButton>
    </div>

    <div class="card table-card">
      <div v-if="loading && !items.length" style="padding: 16px">
        <div class="skeleton" style="height: 40px; margin-bottom: 8px"></div>
        <div class="skeleton" style="height: 40px; margin-bottom: 8px"></div>
        <div class="skeleton" style="height: 40px"></div>
      </div>
      <UiEmpty v-else-if="!items.length" text="暂无知识点，录入错题或手动添加" icon="book" />
      <table v-else class="plain-table">
        <thead>
          <tr>
            <th>标签名</th>
            <th>所属科目</th>
            <th>二级科目</th>
            <th>关联知识点</th>
            <th>创建时间</th>
            <th class="op-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in items" :key="row.id">
            <td class="strong">{{ row.tag_name }}</td>
            <td>{{ subjectName(row.subject_id) }}</td>
            <td>{{ subSubjectName(row.sub_subject_id) || '—' }}</td>
            <td>
              <template v-if="row.related_tags && row.related_tags.length">
                <UiTag
                  v-for="t in row.related_tags"
                  :key="t"
                  :color="'#a16207'"
                  size="sm"
                  clickable
                  style="margin: 2px 4px 2px 0"
                  @click="() => { filters.tag = t; searchKnowledge() }"
                >
                  {{ t }}
                </UiTag>
              </template>
              <span v-else class="muted">—</span>
            </td>
            <td class="muted time">{{ formatTime(row.created_at) }}</td>
            <td class="op-col">
              <div class="ops">
                <button class="op-link primary" @click="practiceTag(row.tag_name)">练习</button>
                <button class="op-link primary" @click="openEdit(row)">编辑</button>
                <button class="op-link warning" :disabled="summarizingId === row.id" @click="autoSummarize(row)">
                  {{ summarizingId === row.id ? '总结中…' : 'AI 总结' }}
                </button>
                <button class="op-link danger" @click="remove(row)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="pagination-wrap">
        <UiPagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          :sizes="[10, 20, 50, 100]"
          @change="loadKnowledge"
        />
      </div>
    </div>

    <KnowledgeEditModal v-model="editVisible" :row="editing" @saved="onSaved" />
    <KnowledgeEditModal v-model="createVisible" :row="null" is-create @saved="onSaved" />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.tag-input { width: 220px; }

.table-card { overflow-x: auto; }

.plain-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 860px;
}
.plain-table th {
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  font-size: 11.5px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--ink-3);
  background: var(--surface-2);
  white-space: nowrap;
}
.plain-table td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-2);
  vertical-align: middle;
}
.plain-table tr:last-child td { border-bottom: none; }
.plain-table .strong { color: var(--ink); font-weight: 650; }
.plain-table .time { font-variant-numeric: tabular-nums; white-space: nowrap; }
.op-col { width: 250px; }
.ops { display: flex; gap: 4px; flex-wrap: wrap; }
.op-link {
  border: none;
  background: transparent;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 3px 7px;
  border-radius: 6px;
}
.op-link:disabled { opacity: 0.5; cursor: not-allowed; }
.op-link.primary { color: var(--accent-ink); }
.op-link.primary:hover { background: var(--accent-soft); }
.op-link.warning { color: var(--gold); }
.op-link.warning:hover { background: var(--gold-soft); }
.op-link.danger { color: var(--red); }
.op-link.danger:hover { background: var(--red-soft); }

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 14px;
}
</style>
