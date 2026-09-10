<script setup>
/** 知识点库：筛选 + 分页表格 + 编辑/创建弹窗 + AI 总结 + 一键练习 */
import { onMounted, reactive, ref, toRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import {
  baseData,
  formatTime,
  subjectColor,
  subjectName,
  subSubjectName,
} from '../composables/useBaseData'
import { useSubSubject } from '../composables/useSubSubject'
import KnowledgeEditModal from '../components/KnowledgeEditModal.vue'
import RichText from '../components/RichText.vue'
import { markdownToPlain } from '../utils/markdown'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiPagination from '../ui/UiPagination.vue'
import Skeleton from '../ui/Skeleton.vue'
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
const detailVisible = ref(false)
const detailItem = ref(null)
const linked = ref(null)
const linkedLoading = ref(false)
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
    // 详情弹窗打开时，列表刷新后同步最新内容（如刚做完 AI 总结）
    if (detailItem.value) {
      const fresh = items.value.find((it) => it.id === detailItem.value.id)
      if (fresh) detailItem.value = fresh
    }
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

/** 卡片摘要：剥掉 Markdown 标记再截断，避免把 ## / ** / 表格竖线显示出来。 */
function plainSummary(text) {
  return markdownToPlain(text)
}

function onSubjectChange() {
  filters.subSubjectId = null
  searchKnowledge()
}

function openDetail(row) {
  detailItem.value = row
  detailVisible.value = true
  loadLinkedMistakes(row)
}

/** 知识点 ↔ 错题：拉取该知识点关联的错题与掌握情况 */
async function loadLinkedMistakes(row) {
  linked.value = null
  linkedLoading.value = true
  try {
    const res = await request.get('/knowledge/linked-mistakes', {
      params: { tag: row.tag_name, limit: 20 },
      silent: true,
    })
    linked.value = res.data.data
  } catch (err) {
    linked.value = null
  } finally {
    linkedLoading.value = false
  }
}

/** 一键练这个知识点下的错题（走按标签筛练习，后端原生支持 tag） */
function practiceLinked() {
  if (!detailItem.value) return
  practiceTag(detailItem.value.tag_name)
}

function practiceOne(id) {
  detailVisible.value = false
  router.push({ path: '/review', query: { mode: 'curve', count: 1, mistake_id: id } })
}

function openEdit(row) {
  detailVisible.value = false
  editing.value = row
  createVisible.value = false
  editVisible.value = true
}

function openCreate() {
  detailVisible.value = false
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
  if (!row || summarizingId.value) return
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

    <div class="filter-bar">
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

    <template v-if="loading && !items.length">
      <div class="k-grid">
        <div v-for="n in 6" :key="n" class="k-card card sk-card">
          <Skeleton variant="text" :width="'55%'" />
          <Skeleton variant="text" :count="2" />
        </div>
      </div>
    </template>
    <UiEmpty v-else-if="!items.length" text="暂无知识点，录入错题或手动添加" icon="book" />
    <template v-else>
      <div class="k-grid">
        <article
          v-for="(row, i) in items"
          :key="row.id"
          class="k-card card"
          role="button"
          tabindex="0"
          :aria-label="`查看知识点 ${row.tag_name}`"
          :style="{ '--enter-delay': Math.min(i, 11) * 50 + 'ms', '--kcol': subjectColor(row.subject_id) }"
          @click="openDetail(row)"
          @keydown.enter.prevent="openDetail(row)"
          @keydown.space.prevent="openDetail(row)"
        >
          <i class="k-spine" aria-hidden="true"></i>
          <div class="k-head">
            <h3 class="k-name">{{ row.tag_name }}</h3>
            <span class="k-time num">{{ formatTime(row.created_at).slice(0, 10) }}</span>
          </div>
          <div class="k-chips">
            <UiTag size="sm" color="var(--teal)" soft>{{ subjectName(row.subject_id) }}</UiTag>
            <UiTag v-if="subSubjectName(row.sub_subject_id)" size="sm" soft>{{ subSubjectName(row.sub_subject_id) }}</UiTag>
          </div>
          <p v-if="row.summary" class="k-summary">{{ plainSummary(row.summary) }}</p>
          <div v-if="row.related_tags && row.related_tags.length" class="k-rel">
            <span class="k-rel-label">关联</span>
            <!-- 关联标签是独立筛选入口：阻止冒泡，避免顺带打开详情 -->
            <UiTag
              v-for="t in row.related_tags"
              :key="t"
              color="var(--gold)"
              size="sm"
              clickable
              @click.stop="() => { filters.tag = t; searchKnowledge() }"
            >
              {{ t }}
            </UiTag>
          </div>
          <div class="k-ops">
            <button class="op-link primary" @click.stop="practiceTag(row.tag_name)"><Icon name="play" :size="12" /> 练习</button>
            <button class="op-link primary" @click.stop="openEdit(row)">编辑</button>
            <button class="op-link warning" :disabled="summarizingId === row.id" @click.stop="autoSummarize(row)">
              {{ summarizingId === row.id ? '总结中…' : 'AI 总结' }}
            </button>
            <button class="op-link danger" @click.stop="remove(row)"><Icon name="trash" :size="12" /></button>
            <span class="k-open-hint" aria-hidden="true">点击查看全文</span>
          </div>
        </article>
      </div>
      <div class="pagination-wrap">
        <UiPagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          :sizes="[10, 20, 50, 100]"
          @change="loadKnowledge"
        />
      </div>
    </template>

    <!-- 知识点详情（点卡片直接查看全文） -->
    <UiModal v-model="detailVisible" :title="detailItem ? detailItem.tag_name : ''" size="lg">
      <div v-if="detailItem" class="k-detail">
        <div class="k-detail-meta">
          <UiTag size="sm" color="var(--teal)" soft>{{ subjectName(detailItem.subject_id) }}</UiTag>
          <UiTag v-if="subSubjectName(detailItem.sub_subject_id)" size="sm" soft>
            {{ subSubjectName(detailItem.sub_subject_id) }}
          </UiTag>
          <span class="k-detail-time num">
            创建于 {{ formatTime(detailItem.created_at).slice(0, 10) }}
          </span>
        </div>

        <div v-if="detailItem.related_tags && detailItem.related_tags.length" class="k-detail-rel">
          <span class="k-rel-label">关联知识点</span>
          <UiTag
            v-for="t in detailItem.related_tags"
            :key="t"
            color="var(--gold)"
            size="sm"
            clickable
            @click="() => { filters.tag = t; detailVisible = false; searchKnowledge() }"
          >
            {{ t }}
          </UiTag>
        </div>

        <div v-if="detailItem.summary" class="k-detail-body">
          <RichText :text="detailItem.summary" />
        </div>
        <p v-else class="muted">这条知识点还没有摘要，可以点「AI 总结」自动生成。</p>

        <!-- 知识点 ↔ 错题：关联错题与掌握情况 -->
        <div class="k-linked">
          <div class="section-label">
            关联错题
            <span v-if="linked && linked.total" class="kl-count">共 {{ linked.total }} 题</span>
            <span v-else-if="!linkedLoading" class="kl-count muted">无</span>
          </div>
          <div v-if="linkedLoading" class="muted">正在统计…</div>
          <template v-else-if="linked && linked.total">
            <div class="k-linked-stats">
              <span class="ls-item"><b>{{ linked.total }}</b> 题</span>
              <span class="ls-item">平均掌握 <b>{{ linked.stats.avg_mastery }}</b></span>
              <span class="ls-item">累计答错 <b>{{ linked.stats.wrong_total }}</b> 次</span>
              <span class="ls-item" :class="{ warn: linked.stats.due_now > 0 }">
                今天到期 <b>{{ linked.stats.due_now }}</b>
              </span>
              <span v-if="linked.stats.never_reviewed" class="ls-item warn">
                从未复习 <b>{{ linked.stats.never_reviewed }}</b>
              </span>
            </div>
            <p v-if="linked.matched_by === 'related_tags'" class="field-hint">
              本知识点名称与错题标签不同名，以下是通过关联标签
              <b>{{ (linked.hit_tags || []).join('、') }}</b> 找到的错题
            </p>
            <ul class="k-linked-list">
              <li v-for="m in linked.items" :key="m.id" class="kl-row">
                <button class="kl-main" :title="m.question" @click="practiceOne(m.id)">
                  <span class="kl-q">{{ plainSummary(m.question).slice(0, 60) }}</span>
                  <span class="kl-meta">
                    答错 {{ m.wrong_count }} 次 · 复习 {{ m.review_count }} 次 · 掌握 {{ m.mastery_level }}
                  </span>
                </button>
                <button class="op-link primary" @click="practiceOne(m.id)">练这题</button>
              </li>
            </ul>
            <p v-if="linked.total > linked.items.length" class="field-hint">
              仅显示前 {{ linked.items.length }} 题（共 {{ linked.total }} 题）
            </p>
          </template>
          <p v-else class="muted">
            还没有关联到错题。错题的「知识点」标签与这条知识点同名时会自动关联；
            也可以在下面补「关联知识点」来建立联系。
          </p>
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="detailVisible = false">关闭</UiButton>
        <UiButton
          v-if="linked && linked.total"
          variant="outline"
          @click="practiceLinked"
        >
          <Icon name="play" :size="12" /> 练这些题（{{ linked.total }}）
        </UiButton>
        <UiButton
          variant="outline"
          :disabled="summarizingId === detailItem?.id"
          @click="autoSummarize(detailItem)"
        >
          {{ summarizingId === detailItem?.id ? '总结中…' : 'AI 总结' }}
        </UiButton>
        <UiButton variant="primary" @click="openEdit(detailItem)">编辑</UiButton>
      </template>
    </UiModal>

    <KnowledgeEditModal v-model="editVisible" :row="editing" @saved="onSaved" />
    <KnowledgeEditModal v-model="createVisible" :row="null" is-create @saved="onSaved" />
  </div>
</template>

<style scoped>
/* 玻璃筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding: 14px 18px;
  position: relative;
  /* backdrop-filter 会创建层叠上下文：不给 z-index 的话，下拉菜单会被后渲染的卡片盖住 */
  z-index: 5;
  border: 1px solid transparent;
  border-radius: var(--r-lg);
  background:
    linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(135deg, color-mix(in srgb, var(--teal) 16%, transparent), transparent 45%, color-mix(in srgb, var(--gold) 14%, transparent)) border-box;
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(10px) saturate(1.15);
}
.tag-input { width: 220px; }

/* 知识笺卡片墙 */
.k-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.k-card {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 15px 16px 13px 21px;
  cursor: pointer;
  transition: border-color 0.2s var(--ease), box-shadow 0.3s var(--ease);
  animation: kcard-in 0.5s var(--ease) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes kcard-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}
.k-card:hover {
  border-color: color-mix(in srgb, var(--kcol) 45%, var(--line));
  box-shadow: var(--shadow-2);
}
/* 注意：卡片 hover 不做 translateY 位移。
   整卡可点后，鼠标停在卡片下沿时上浮会让指针落到卡片外，触发 mouseleave、
   卡片落回、指针又进入……形成抖动循环（点了像没反应）。用边框+阴影表达 hover 即可。 */
.k-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
/* 卡片内可交互元素（关联标签、操作按钮）自带 @click.stop，独立生效 */
.k-open-hint {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--ink-3);
  opacity: 0;
  transition: opacity 0.2s var(--ease);
  white-space: nowrap;
}
.k-card:hover .k-open-hint,
.k-card:focus-within .k-open-hint { opacity: 1; }
.k-spine {
  position: absolute;
  left: 0;
  top: 13px;
  bottom: 13px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: linear-gradient(180deg, var(--kcol), color-mix(in srgb, var(--kcol) 35%, transparent));
  opacity: 0.85;
  transition: width 0.25s var(--spring);
  /* 色脊是纯装饰：不参与命中测试 */
  pointer-events: none;
}
.k-card:hover .k-spine { width: 6px; opacity: 1; }
.sk-card { animation: none; }

.k-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}
.k-name {
  font-family: var(--font-display);
  font-size: 15.5px;
  font-weight: 700;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.k-card:hover .k-name { color: var(--kcol); }
.k-time { font-size: 11.5px; color: var(--ink-3); flex: none; }
.k-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.k-summary {
  margin: 0;
  font-size: 12.8px;
  color: var(--ink-2);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.k-rel { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.k-rel-label { font-size: 11px; font-weight: 700; color: var(--ink-3); letter-spacing: 0.08em; }

.k-ops {
  margin-top: auto;
  padding-top: 9px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  gap: 4px;
}
.op-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 7px;
  transition: background 0.14s var(--ease);
}
.op-link:disabled { opacity: 0.5; cursor: not-allowed; }
.op-link.primary { color: var(--accent-ink); }
.op-link.primary:hover { background: var(--accent-soft); }
.op-link.warning { color: var(--gold); }
.op-link.warning:hover { background: var(--gold-soft); }
.op-link.danger { color: var(--red); }
.op-link.danger:hover { background: var(--red-soft); }

/* 知识点详情弹窗 */
.k-detail { display: flex; flex-direction: column; gap: 14px; }
.k-detail-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.k-detail-time { font-size: 12px; color: var(--ink-3); margin-left: auto; }
.k-detail-rel { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.k-detail-body {
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 14px 16px;
  background: var(--surface-2);
}
.muted { color: var(--ink-3); font-size: 13px; }

/* 知识点 ↔ 错题链接 */
.k-linked { display: flex; flex-direction: column; gap: 10px; }
/* 弹窗正文可能很长（知识点摘要+关联错题），用一条分隔线把两者分开，滚动时更清楚 */
.k-linked { border-top: 1px dashed var(--line); padding-top: 12px; }
.kl-count { margin-left: 6px; font-weight: 700; color: var(--accent-ink); font-size: 12px; }
.kl-count.muted { color: var(--ink-3); font-weight: 600; }
.k-linked-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding: 10px 12px;
  border-radius: var(--r-md);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 12.5px;
  color: var(--ink-2);
}
.ls-item b { color: var(--ink); font-size: 14px; }
.ls-item.warn b { color: var(--accent-ink); }
.field-hint { font-size: 12px; color: var(--ink-3); margin: 0; }
.k-linked-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 260px;
  overflow-y: auto;
}
.kl-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  transition: background 0.14s var(--ease);
}
.kl-row:hover { background: var(--surface-2); }
.kl-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  padding: 0;
  font: inherit;
}
.kl-q {
  font-size: 12.8px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kl-meta { font-size: 11px; color: var(--ink-3); }

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  padding-bottom: 8px;
}
</style>
