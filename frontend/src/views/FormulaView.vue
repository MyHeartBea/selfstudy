<script setup>
/** 公式背诵库：分类/搜索 + 卡片网格 + 详情/编辑 + 背诵模式 */
import { computed, onMounted, reactive, ref } from 'vue'

import request from '../api/request'
import RichText from '../components/RichText.vue'
import { formatTime } from '../composables/useBaseData'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiModal from '../ui/UiModal.vue'

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
  // 过卡循环：没记住的排到队尾，直到全部记住
  reciteQueue.value = filteredItems.value.slice()
  reciteKnown.value = 0
  reciteTotal.value = reciteQueue.value.length
  reciteRevealed.value = false
  memorizeVisible.value = true
}

const reciteQueue = ref([])
const reciteKnown = ref(0)
const reciteTotal = ref(0)

function markRecite(known) {
  if (!reciteQueue.value.length) return
  const current = reciteQueue.value[0]
  if (known) {
    reciteQueue.value.shift()
    reciteKnown.value += 1
  } else {
    // 没记住：移到队尾，稍后再来
    reciteQueue.value.push(reciteQueue.value.shift())
  }
  reciteRevealed.value = false
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
    toast.warning('请填写公式标题')
    return
  }
  if (!form.content.trim()) {
    toast.warning('请填写公式内容')
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
      toast.success('公式已更新')
    } else {
      await request.post('/formulas', payload)
      toast.success('公式已添加')
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
  const ok = await confirmDialog({
    title: '删除确认',
    message: `确定删除“${item.title}”吗？`,
    danger: true,
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await request.delete(`/formulas/${item.id}`)
    toast.success('公式已删除')
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
        <UiButton v-if="filteredItems.length" variant="outline" @click="openMemorize">
          背诵模式
        </UiButton>
        <UiButton variant="primary" @click="openCreate">新增公式</UiButton>
      </div>
    </div>

    <div class="card card-pad filter-bar">
      <UiSelect
        v-model="filters.category"
        :options="categories"
        placeholder="全部分类"
        clearable
        compact
      />
      <input
        v-model="filters.search"
        class="field-input search-input"
        placeholder="搜索标题或公式"
      />
      <span class="count-tip">共 {{ filteredItems.length }} 条</span>
    </div>

    <UiEmpty
      v-if="!filteredItems.length && !loading"
      text="暂无公式，点击右上角新增"
      icon="sigma"
    />
    <div v-else class="formula-grid">
      <article
        v-for="item in filteredItems"
        :key="item.id"
        class="formula-card card"
      >
        <div class="formula-head">
          <UiTag size="sm">{{ item.category }}</UiTag>
          <span class="formula-title" role="button" tabindex="0" @click="openDetail(item)" @keydown.enter="openDetail(item)">
            {{ item.title }}
          </span>
        </div>
        <div class="formula-preview">{{ plainPreview(item) }}</div>
        <div class="formula-foot">
          <span class="muted">{{ formatTime(item.updated_at || item.created_at) }}</span>
          <div class="formula-actions">
            <button class="op-link" @click="openDetail(item)">查看</button>
            <button class="op-link" @click="openEdit(item)">编辑</button>
            <button class="op-link danger" @click="remove(item)">删除</button>
          </div>
        </div>
      </article>
    </div>

    <!-- 背诵模式（过卡循环） -->
    <UiModal v-model="memorizeVisible" title="背诵模式 · 过卡循环" size="lg">
      <div v-if="reciteQueue.length">
        <div class="memorize-head">
          <UiTag size="sm">{{ reciteQueue[0].category }}</UiTag>
          <span class="count-tip">
            剩余 {{ reciteQueue.length }} / {{ reciteTotal }} · 已记住 {{ reciteKnown }}
          </span>
        </div>
        <div class="recite-progress">
          <div class="recite-progress-inner" :style="{ width: (reciteKnown / Math.max(1, reciteTotal)) * 100 + '%' }"></div>
        </div>
        <h3 class="memorize-title">{{ reciteQueue[0].title }}</h3>
        <div v-if="reciteRevealed" class="knowledge-preview">
          <RichText :text="reciteQueue[0].content" />
        </div>
        <UiButton
          v-if="!reciteRevealed"
          variant="primary"
          size="lg"
          style="margin-top: 12px"
          @click="reciteRevealed = true"
        >
          显示内容
        </UiButton>
      </div>
      <div v-else class="recite-complete">
        <Icon name="check" :size="34" />
        <h3>全部记住！</h3>
        <p class="muted">本轮 {{ reciteTotal }} 条公式已全部过完。</p>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="memorizeVisible = false">退出</UiButton>
        <template v-if="reciteQueue.length">
          <UiButton variant="outline" @click="markRecite(false)">没记住，待会再来</UiButton>
          <UiButton v-if="reciteRevealed" variant="primary" @click="markRecite(true)">记住了</UiButton>
        </template>
      </template>
    </UiModal>

    <!-- 详情 -->
    <UiModal v-model="detailVisible" :title="detailItem ? detailItem.title : ''" size="lg">
      <div v-if="detailItem">
        <UiTag size="sm" style="margin-bottom: 12px">{{ detailItem.category }}</UiTag>
        <RichText :text="detailItem.content" />
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="detailVisible = false">关闭</UiButton>
      </template>
    </UiModal>

    <!-- 新增/编辑 -->
    <UiModal v-model="dialogVisible" :title="editingId ? '编辑公式' : '新增公式'" size="md">
      <div class="f-form">
        <div class="field">
          <label class="field-label">分类</label>
          <UiSelect v-model="form.category" :options="categories" />
        </div>
        <div class="field">
          <label class="field-label">标题</label>
          <input v-model="form.title" class="field-input" placeholder="如：基本积分表" />
        </div>
        <div class="field">
          <label class="field-label">内容</label>
          <textarea
            v-model="form.content"
            class="field-input"
            rows="10"
            placeholder="支持 $...$ 公式、Markdown 表格和列表"
          ></textarea>
        </div>
        <div v-if="form.content.trim()" class="knowledge-preview">
          <div class="section-label">预览</div>
          <RichText :text="form.content" />
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="dialogVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="saving" @click="save">保存</UiButton>
      </template>
    </UiModal>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.search-input { width: 240px; }

.formula-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.formula-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  cursor: default;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.formula-card:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
  box-shadow: var(--shadow-2);
  transform: translateY(-2px);
}

.formula-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.formula-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--ink);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.formula-title:hover { color: var(--accent-ink); }

.formula-preview {
  font-size: 12.5px;
  color: var(--ink-3);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 40px;
}

.formula-foot {
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}
.formula-actions { display: flex; gap: 2px; }
.op-link {
  border: none;
  background: transparent;
  color: var(--accent-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 3px 7px;
  border-radius: 6px;
}
.op-link:hover { background: var(--accent-soft); }
.op-link.danger { color: var(--red); }
.op-link.danger:hover { background: var(--red-soft); }

.memorize-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.recite-progress {
  height: 6px;
  border-radius: 999px;
  background: var(--bg-soft);
  overflow: hidden;
  margin-bottom: 14px;
}
.recite-progress-inner {
  height: 100%;
  border-radius: 999px;
  background: var(--green);
  transition: width 0.4s cubic-bezier(0.22, 0.8, 0.36, 1);
}
.recite-complete {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 0;
  color: var(--green);
  text-align: center;
}
.recite-complete h3 {
  font-family: var(--font-display);
  color: var(--ink);
}
.memorize-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  margin: 6px 0 12px;
}
.knowledge-preview {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px 16px;
  background: var(--surface-2);
}

.f-form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 12.5px; font-weight: 700; color: var(--ink-2); }
</style>
