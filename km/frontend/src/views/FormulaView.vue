<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import request from '../api/request'
import RichText from '../components/RichText.vue'
import { formatTime } from '../composables/useBaseData'

const categories = [
  '高等数学',
  '线性代数',
  '概率统计',
  '英语背诵',
  '政治背诵',
  '408背诵',
  '其他',
]

const loading = ref(false)
const items = ref([])
const filters = reactive({
  category: '',
  search: '',
})
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailItem = ref(null)
const memorizeVisible = ref(false)
const memorizeIndex = ref(0)
const memorizeRevealed = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({
  category: '高等数学',
  title: '',
  content: '',
})

const filteredItems = computed(() => {
  let list = items.value.slice()
  if (filters.category) {
    list = list.filter((item) => item.category === filters.category)
  }
  if (filters.search.trim()) {
    const keyword = filters.search.trim().toLowerCase()
    list = list.filter(
      (item) =>
        (item.title || '').toLowerCase().includes(keyword) ||
        (item.content || '').toLowerCase().includes(keyword),
    )
  }
  return list
})

async function loadFormulas() {
  loading.value = true
  try {
    const res = await request.get('/formulas')
    items.value = res.data.data || []
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, {
    category: '高等数学',
    title: '',
    content: '',
  })
  dialogVisible.value = true
}

function openDetail(item) {
  detailItem.value = item
  detailVisible.value = true
}

function plainPreview(item) {
  const line =
    String(item.content || '')
      .split('\n')
      .find(
        (value) =>
          value.trim() &&
          !value.trim().startsWith('#') &&
          !value.trim().startsWith('|'),
      ) || ''
  return line.replace(/[$*`]/g, '').slice(0, 80)
}

function openMemorize() {
  memorizeIndex.value = 0
  memorizeRevealed.value = false
  memorizeVisible.value = true
}

function moveMemorize(step) {
  const total = filteredItems.value.length
  if (!total) return
  memorizeIndex.value = (memorizeIndex.value + step + total) % total
  memorizeRevealed.value = false
}

function openEdit(item) {
  editingId.value = item.id
  Object.assign(form, {
    category: item.category || '高等数学',
    title: item.title || '',
    content: item.content || '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写公式标题')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请填写公式内容')
    return
  }
  saving.value = true
  try {
    const payload = {
      category: form.category,
      title: form.title.trim(),
      content: form.content.trim(),
    }
    if (editingId.value) {
      await request.put(`/formulas/${editingId.value}`, payload)
      ElMessage.success('公式已更新')
    } else {
      await request.post('/formulas', payload)
      ElMessage.success('公式已添加')
    }
    dialogVisible.value = false
    loadFormulas()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    saving.value = false
  }
}

async function remove(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除“${item.title}”吗？`,
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
    await request.delete(`/formulas/${item.id}`)
    ElMessage.success('公式已删除')
    loadFormulas()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(loadFormulas)
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Formula Deck</div>
        <h2>公式背诵库</h2>
        <p class="view-desc">常用公式集中管理、检索与背诵。</p>
      </div>
      <div class="header-actions">
        <el-button
          v-if="filteredItems.length"
          type="warning"
          plain
          @click="openMemorize"
        >
          背诵模式
        </el-button>
        <el-button type="primary" @click="openCreate">新增公式</el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true">
        <el-form-item label="分类">
          <el-select
            v-model="filters.category"
            clearable
            placeholder="全部分类"
            style="width: 160px"
          >
            <el-option
              v-for="c in categories"
              :key="c"
              :label="c"
              :value="c"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            clearable
            placeholder="搜索标题或公式"
            style="width: 220px"
          />
        </el-form-item>
        <el-form-item>
          <span class="count-tip">共 {{ filteredItems.length }} 条</span>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-loading="loading">
      <el-empty
        v-if="!filteredItems.length"
        description="暂无公式，点击右上角新增"
      />
      <div v-else class="formula-grid">
        <el-card
          v-for="item in filteredItems"
          :key="item.id"
          shadow="hover"
          class="formula-card"
        >
          <div class="formula-head">
            <el-tag size="small" effect="plain">{{ item.category }}</el-tag>
            <span
              class="formula-title"
              title="查看内容"
              @click="openDetail(item)"
            >
              {{ item.title }}
            </span>
            <div class="formula-actions">
              <el-button size="small" type="primary" link @click="openDetail(item)">
                查看
              </el-button>
              <el-button size="small" type="primary" link @click="openEdit(item)">
                编辑
              </el-button>
              <el-button size="small" type="danger" link @click="remove(item)">
                删除
              </el-button>
            </div>
          </div>
          <div class="formula-preview">{{ plainPreview(item) }}</div>
          <div class="formula-foot">
            <span>{{ formatTime(item.updated_at || item.created_at) }}</span>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog
      v-model="memorizeVisible"
      title="背诵模式"
      width="760px"
      top="5vh"
    >
      <div v-if="filteredItems.length">
        <div class="memorize-head">
          <el-tag size="small" effect="plain">
            {{ filteredItems[memorizeIndex].category }}
          </el-tag>
          <span>
            {{ memorizeIndex + 1 }} / {{ filteredItems.length }}
          </span>
        </div>
        <h3 style="color: #1d3a5f; margin: 10px 0">
          {{ filteredItems[memorizeIndex].title }}
        </h3>
        <div v-if="memorizeRevealed" class="knowledge-preview">
          <RichText :text="filteredItems[memorizeIndex].content" />
        </div>
        <el-button
          v-if="!memorizeRevealed"
          type="primary"
          size="large"
          style="margin-top: 12px"
          @click="memorizeRevealed = true"
        >
          显示内容
        </el-button>
      </div>
      <template #footer>
        <el-button @click="memorizeVisible = false">退出</el-button>
        <el-button :disabled="filteredItems.length < 2" @click="moveMemorize(-1)">
          上一个
        </el-button>
        <el-button type="primary" @click="moveMemorize(1)">
          下一个
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailVisible"
      :title="detailItem ? detailItem.title : ''"
      width="840px"
      top="5vh"
    >
      <div v-if="detailItem">
        <el-tag size="small" effect="plain" style="margin-bottom: 10px">
          {{ detailItem.category }}
        </el-tag>
        <RichText :text="detailItem.content" />
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑公式' : '新增公式'"
      width="760px"
      top="5vh"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 220px">
            <el-option
              v-for="c in categories"
              :key="c"
              :label="c"
              :value="c"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="如：基本积分表" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="支持 $...$ 公式、Markdown 表格和列表"
          />
        </el-form-item>
        <div v-if="form.content.trim()" class="knowledge-preview">
          <div class="section-label">预览</div>
          <RichText :text="form.content" />
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
