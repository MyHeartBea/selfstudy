<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import {
  baseData,
  formatTime,
  subjectName,
  subSubjectName,
} from '../composables/useBaseData'
import KnowledgeEditDialog from '../components/KnowledgeEditDialog.vue'

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
const editing = ref(null)
const summarizingId = ref(null)

const subSubjectOptions = computed(() => {
  if (!filters.subjectId) return []
  return baseData.subSubjects.filter((item) => item.subject_id === filters.subjectId)
})

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

function handleSizeChange() {
  page.value = 1
  loadKnowledge()
}

function handlePageChange() {
  loadKnowledge()
}

function resetFilters() {
  filters.subjectId = null
  filters.subSubjectId = null
  filters.tag = ''
  page.value = 1
  loadKnowledge()
}

function practiceTag(tag) {
  router.push({
    path: '/review',
    query: { mode: 'curve', count: 10, tag },
  })
}

function onSubjectChange() {
  filters.subSubjectId = null
  page.value = 1
  loadKnowledge()
}

function onSubSubjectChange() {
  page.value = 1
  loadKnowledge()
}

function openEdit(row) {
  editing.value = row
  editVisible.value = true
}

function onSaved() {
  editVisible.value = false
  loadKnowledge()
}

async function autoSummarize(row) {
  summarizingId.value = row.id
  try {
    await request.post(`/knowledge/${row.id}/auto-summarize`)
    ElMessage.success('总结已生成')
    loadKnowledge()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    summarizingId.value = null
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除知识点“${row.tag_name}”吗？不影响已关联错题。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch (err) {
    return
  }
  try {
    await request.delete(`/knowledge/${row.id}`)
    ElMessage.success('删除成功')
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
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="科目">
          <el-select
            v-model="filters.subjectId"
            clearable
            placeholder="全部科目"
            style="width: 180px"
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
            style="width: 180px"
            :disabled="!subSubjectOptions.length"
            @change="onSubSubjectChange"
          >
            <el-option
              v-for="s in subSubjectOptions"
              :key="s.id"
              :label="s.name"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input
            v-model="filters.tag"
            clearable
            placeholder="搜索知识点标签"
            style="width: 220px"
            @keyup.enter="searchKnowledge"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="searchKnowledge">
            搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="tag_name" label="标签名" min-width="150" />
        <el-table-column label="所属科目" min-width="150">
          <template #default="{ row }">{{ subjectName(row.subject_id) }}</template>
        </el-table-column>
        <el-table-column label="二级科目" min-width="140">
          <template #default="{ row }">
            {{ subSubjectName(row.sub_subject_id) || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="关联知识点" min-width="220">
          <template #default="{ row }">
            <template v-if="row.related_tags && row.related_tags.length">
              <el-tag
                v-for="t in row.related_tags"
                :key="t"
                size="small"
                type="warning"
                class="tag-item"
                style="margin: 2px 4px 2px 0; cursor: pointer"
                @click="filters.tag = t; searchKnowledge()"
              >
                {{ t }}
              </el-tag>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="175">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="practiceTag(row.tag_name)">
              练习
            </el-button>
            <el-button size="small" type="primary" link @click="openEdit(row)">
              编辑
            </el-button>
            <el-button
              size="small"
              type="warning"
              link
              :loading="summarizingId === row.id"
              @click="autoSummarize(row)"
            >
              AI 总结
            </el-button>
            <el-button size="small" type="danger" link @click="remove(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <KnowledgeEditDialog v-model="editVisible" :row="editing" @saved="onSaved" />
  </div>
</template>

<style scoped>
.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
