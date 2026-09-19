<script setup>
/** 作文档案：AI 批改过的英语作文历史（分数趋势 + 逐句改错回看）。 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import request from '../api/request'
import { confirmDialog } from '../ui/confirm'
import { toast } from '../ui/toast'
import { formatTime } from '../composables/useBaseData'
import { useResourceList } from '../composables/useResourceList'
import EssayGradeResult from '../components/EssayGradeResult.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'
import UiModal from '../ui/UiModal.vue'
import UiPagination from '../ui/UiPagination.vue'
import Skeleton from '../ui/Skeleton.vue'
import Icon from '../ui/Icon.vue'
import { ESSAY_KINDS, essayKindMeta } from '../composables/essayKinds'

const route = useRoute()

const page = ref(1)
const pageSize = ref(15)
const kind = ref('')
// 命令面板跳回来时带 ?search=（后端按题干/正文 LIKE 过滤）
const search = ref(route.query.search ? String(route.query.search) : '')

const detail = ref(null)
const detailVisible = ref(false)
const detailTranscript = ref('')

const {
  items,
  total,
  loading,
  loadError,
  load: loadList,
} = useResourceList(async () => {
  const res = await request.get('/essays', {
    params: {
      page: page.value,
      page_size: pageSize.value,
      kind: kind.value || undefined,
      search: search.value.trim() || undefined,
    },
    silent: true,
  })
  return res.data.data
})

const kindOptions = computed(() => [{ value: '', label: '全部类型' }, ...ESSAY_KINDS])

// 分数趋势条：按时间正序，高度 = 得分率
const trend = computed(() =>
  [...items.value]
    .reverse()
    .map((r) => ({ id: r.id, pct: Math.round((r.score / (r.max_score || 1)) * 100) })),
)

const avgPct = computed(() => {
  if (!items.value.length) return 0
  const sum = items.value.reduce((acc, r) => acc + r.score / (r.max_score || 1), 0)
  return Math.round((sum / items.value.length) * 100)
})

function onFilterChange() {
  page.value = 1
  loadList()
}

let searchTimer = null
function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(onFilterChange, 300)
}

async function openDetail(row) {
  try {
    const res = await request.get(`/essays/${row.id}`, { silent: true })
    const data = res.data.data || {}
    detail.value = { ...data, ...(data.result || {}) }
    detailTranscript.value = data.result?.raw_transcript || data.essay_text || ''
    detailVisible.value = true
  } catch (err) {
    toast.error(`打开失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
  }
}

async function removeOne(row) {
  const yes = await confirmDialog({
    title: '删除这条作文记录？',
    message: `${essayKindMeta(row.kind).label} · ${row.score}/${row.max_score} 分，删除后不可恢复。`,
    danger: true,
  })
  if (!yes) return
  try {
    await request.delete(`/essays/${row.id}`, { silent: true })
    toast.success('已删除')
    detailVisible.value = false
    await loadList()
  } catch (err) {
    toast.error(`删除失败：${err?.response?.data?.message || err?.message || '未知错误'}`)
  }
}

onMounted(loadList)
onUnmounted(() => {
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Essay Grader</div>
        <h2>作文档案</h2>
        <p class="view-desc">
          每篇批改都会存档：分数档位、四维得分、逐句改错与同题范文。
          <RouterLink to="/capture" class="ea-new">去录入页批改新作文</RouterLink>
        </p>
      </div>
      <div v-if="items.length" class="ea-summary">
        <div class="ea-avg">
          <span class="ea-avg-num serif">{{ avgPct }}</span>
          <span class="ea-avg-label">本页平均得分率 %</span>
        </div>
        <div class="ea-trend" aria-hidden="true">
          <i v-for="t in trend" :key="t.id" :style="{ height: Math.max(8, t.pct) + '%' }"></i>
        </div>
      </div>
    </div>

    <div class="list-toolbar">
      <div class="ea-search">
        <Icon name="search" :size="15" class="ea-search-icon" />
        <input
          v-model="search"
          class="field-input"
          type="search"
          placeholder="搜索题目要求或作文正文"
          @keyup.enter="onFilterChange"
          @input="onSearchInput"
        />
      </div>
      <UiSelect v-model="kind" :options="kindOptions" compact @change="onFilterChange" />
      <UiButton size="sm" variant="ghost" @click="loadList">
        <Icon name="refresh" :size="14" />
        刷新
      </UiButton>
    </div>

    <div v-if="loading" class="ea-grid">
      <div v-for="i in 4" :key="i" class="ea-skel card">
        <Skeleton variant="rect" :height="132" :radius="12" />
      </div>
    </div>

    <UiLoadError v-else-if="loadError" @retry="loadList" />

    <UiEmpty
      v-else-if="!items.length"
      seal="文"
      :text="search.trim() ? '没有匹配的作文，换个关键词试试' : '还没有批改记录'"
    />

    <template v-else>
      <div class="ea-grid">
        <article
          v-for="(row, i) in items"
          :key="row.id"
          class="ea-card card"
          role="button"
          tabindex="0"
          :aria-label="`查看作文 ${row.id}`"
          :style="{ '--enter-delay': `calc(${Math.min(i, 11)} * var(--stagger-1))` }"
          @click="openDetail(row)"
          @keydown.enter.prevent="openDetail(row)"
          @keydown.space.prevent="openDetail(row)"
        >
          <div class="ea-card-head">
            <span class="ea-score serif">{{ row.score }}</span>
            <span class="ea-max">/ {{ row.max_score }}</span>
            <UiTag class="ea-kind" size="sm" soft>{{ essayKindMeta(row.kind).label }}</UiTag>
          </div>
          <p class="ea-excerpt">{{ row.excerpt || '（无正文）' }}</p>
          <div class="ea-card-foot">
            <span class="ea-time num">{{ formatTime(row.created_at).slice(0, 16) }}</span>
            <button
              type="button"
              class="ea-del"
              aria-label="删除这条作文记录"
              @click.stop="removeOne(row)"
            >
              <Icon name="trash" :size="14" />
            </button>
          </div>
        </article>
      </div>
      <UiPagination
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        :sizes="[15, 30, 60]"
        @change="loadList"
      />
    </template>

    <UiModal v-model="detailVisible" title="作文批改详情" size="lg">
      <div v-if="detail" class="ea-detail">
        <EssayGradeResult :result="detail" :transcript="detailTranscript" />
        <div v-if="detail.prompt_text" class="ea-prompt">
          <h4>题目要求</h4>
          <pre>{{ detail.prompt_text }}</pre>
        </div>
      </div>
    </UiModal>
  </div>
</template>

<style scoped>
/* 玻璃筛选栏必须带 z-index，否则内部下拉被后渲染卡片盖住 */
.list-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.ea-new {
  margin-left: 6px;
  color: var(--accent-ink);
  text-decoration: none;
  border-bottom: 1px dashed var(--accent-ring);
}
.ea-new:hover {
  border-bottom-style: solid;
}
.ea-search {
  position: relative;
  display: flex;
  align-items: center;
}
.ea-search-icon {
  position: absolute;
  left: 11px;
  color: var(--ink-3);
  pointer-events: none;
}
.ea-search .field-input {
  width: 240px;
  padding-left: 33px;
}
.ea-summary {
  display: flex;
  align-items: flex-end;
  gap: 14px;
}
.ea-avg {
  display: grid;
  justify-items: end;
  line-height: 1;
}
.ea-avg-num {
  font-size: var(--fs-display);
  font-weight: 900;
  color: var(--accent);
}
.ea-avg-label {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ink-3);
}
.ea-trend {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 46px;
}
.ea-trend i {
  width: 6px;
  border-radius: 3px 3px 0 0;
  background: var(--accent-grad);
  opacity: 0.75;
}
.ea-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.ea-card {
  position: relative;
  display: grid;
  gap: 10px;
  align-content: start;
  padding: 16px;
  cursor: pointer;
  overflow: hidden;
  transition:
    border-color 0.24s var(--ease),
    box-shadow 0.24s var(--ease);
  animation: ea-in 0.4s var(--ease-enter) backwards;
  animation-delay: var(--enter-delay, 0ms);
}
.ea-skel {
  padding: 16px;
}
@keyframes ea-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
}
/* hover 不做 translateY 位移（卡片边缘抖动循环） */
.ea-card:hover,
.ea-card:focus-visible {
  border-color: var(--accent-ring);
  box-shadow: var(--shadow-2);
}
.ea-card-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.ea-score {
  font-size: 28px;
  font-weight: 900;
  color: var(--ink);
  line-height: 1;
}
.ea-max {
  font-size: 12px;
  color: var(--ink-3);
}
.ea-kind {
  margin-left: auto;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ea-excerpt {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ea-card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--ink-3);
}
.ea-del {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: var(--surface);
  color: var(--ink-3);
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.ea-del:hover {
  color: var(--red);
  border-color: color-mix(in srgb, var(--red) 45%, transparent);
}
.ea-detail {
  display: grid;
  gap: 16px;
}
.ea-prompt h4 {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--ink);
}
.ea-prompt pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-sm);
  background: var(--surface-2);
  border: 1px solid var(--line);
  font-size: 12.5px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--ink-2);
  font-family: inherit;
}
</style>
