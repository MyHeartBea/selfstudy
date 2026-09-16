<!--
  KnowledgeView —— 知识点库（知识笺）
  ---------------------------------------------------------------------------
  交互语义：知识点 = 标本（宣纸墙上的知识笺）；关联错题 = 它沉淀下来的层理。

  契约要点：
    GET /api/knowledge 一直返回分页对象 { items, total, page, page_size }（与 mistakes 不同）
    GET /api/knowledge/tags 返回 [{ tag, mistake_count }]（对象数组）
    POST /api/knowledge/{id}/auto-summarize 触发 AI 总结（会花钱，所以只在用户点击时调用）

  设计取舍：整块可点开详情（InkCard 的教训）；AI 总结按钮 @click.stop，
  不与"打开详情"冲突。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { baseApi, knowledgeApi } from '../core/api'
import { toast } from '../ui/toast'
import InkCard from '../ui/InkCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'
import UiModal from '../ui/UiModal.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'

const PAGE_SIZE = 24

const loading = ref(true)
const errorText = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)

const filters = reactive({ search: '', subject_id: '' })
const subjects = ref([])
const tags = ref([])

const detailOpen = ref(false)
const detail = ref(null)
const linked = ref(null)
const linkedLoading = ref(false)
/** 正在 AI 总结的知识点 id（用于按钮 loading） */
const summarizingId = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const subjectName = (id) => subjects.value.find((s) => s.id === id)?.name || '未分科'
const SUBJECT_OPTIONS = computed(() => [
  { value: '', label: '全部科目' },
  ...subjects.value.map((s) => ({ value: String(s.id), label: s.name })),
])

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const params = { page: page.value, page_size: PAGE_SIZE }
    if (filters.subject_id) params.subject_id = Number(filters.subject_id)
    if (filters.search.trim()) params.tag = filters.search.trim()
    const data = await knowledgeApi.list(params)
    // knowledge 一直是分页对象；这里仍留一个数组兜底，避免后端行为变化时静默失败
    if (Array.isArray(data)) {
      items.value = data
      total.value = data.length
    } else {
      items.value = data?.items || []
      total.value = data?.total ?? items.value.length
    }
  } catch (e) {
    errorText.value = e?.message || '无法载入知识点'
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const [s, t] = await Promise.allSettled([baseApi.subjects(), knowledgeApi.tags(120)])
  if (s.status === 'fulfilled') subjects.value = s.value || []
  if (t.status === 'fulfilled') tags.value = t.value || []
}

async function openDetail(row) {
  detail.value = row
  detailOpen.value = true
  linked.value = null
  linkedLoading.value = true
  try {
    const data = await knowledgeApi.linkedMistakes({ tag: row.tag_name })
    linked.value = data && Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
  } catch {
    linked.value = []
  } finally {
    linkedLoading.value = false
  }
}

/** AI 总结：需要花钱，所以只在用户显式点击时调用 */
async function summarize(row) {
  if (summarizingId.value) return
  summarizingId.value = row.id
  try {
    const updated = await knowledgeApi.summarize(row.id)
    if (updated && typeof updated === 'object') Object.assign(row, updated)
    toast.success('已重新总结')
  } catch (e) {
    toast.error(e?.message || '总结失败')
  } finally {
    summarizingId.value = null
  }
}

function applyFilters() {
  page.value = 1
  load()
}

let timer = 0
watch(
  () => filters.search,
  () => {
    clearTimeout(timer)
    timer = setTimeout(applyFilters, 340)
  },
)

/** 摘要预览：去掉 markdown 记号，只留文字（卡片不渲染富文本，避免一屏里公式过多） */
function plain(text) {
  return String(text || '')
    .replace(/[#*_`>$-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

onMounted(() => {
  loadMeta()
  load()
})
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <main id="main" class="pad">
    <header class="head">
      <span class="mono">[04] SPECIMENS · 知识点库</span>
      <span class="mono">{{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
    </header>

    <div class="filters">
      <UiField
        v-model="filters.search"
        label="按标签筛选"
        :placeholder="tags.length ? `例如 ${tags[0]?.tag || ''}` : '标签名'"
        @enter="applyFilters"
      />
      <UiSelect
        v-model="filters.subject_id"
        :options="SUBJECT_OPTIONS"
        label="科目"
        @change="applyFilters"
      />
    </div>

    <div v-if="tags.length" class="tagbar">
      <button
        v-for="t in tags.slice(0, 12)"
        :key="t.tag"
        type="button"
        class="tbtn"
        :class="{ on: filters.search === t.tag }"
        @click="((filters.search = t.tag), applyFilters())"
      >
        {{ t.tag }}<span class="mono n">{{ t.mistake_count }}</span>
      </button>
    </div>

    <UiEmpty v-if="loading" variant="skeleton" thumb :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty
      v-else-if="!items.length"
      title="还没有知识点"
      hint="录入错题后 AI 会自动归纳，也可以手动添加"
    />

    <template v-else>
      <div class="wall">
        <InkCard v-for="row in items" :key="row.id" spine="var(--vein)" @select="openDetail(row)">
          <div class="chead">
            <h3 class="kname">{{ row.tag_name }}</h3>
            <span class="mono subj">{{ subjectName(row.subject_id) }}</span>
          </div>
          <p v-if="row.summary" class="ksum">{{ plain(row.summary).slice(0, 120) }}</p>
          <p v-else class="ksum none">尚无摘要</p>

          <div class="cfoot">
            <UiTag v-for="t in (row.related_tags || []).slice(0, 3)" :key="t" tone="gold" size="sm">
              {{ t }}
            </UiTag>
            <UiButton
              variant="quiet"
              size="sm"
              class="sum"
              :loading="summarizingId === row.id"
              @click.stop="summarize(row)"
            >
              AI 总结
            </UiButton>
          </div>
        </InkCard>
      </div>

      <div class="pager">
        <UiButton :disabled="page <= 1" @click="((page -= 1), load())">上一页</UiButton>
        <span class="mono pnum">{{ page }} / {{ totalPages }}</span>
        <UiButton :disabled="page >= totalPages" @click="((page += 1), load())">下一页</UiButton>
      </div>
    </template>

    <!-- 详情：摘要全文 + 关联错题 -->
    <UiModal v-model="detailOpen" :title="detail ? detail.tag_name : '知识点'" size="lg">
      <div v-if="detail" class="det">
        <div class="dmeta">
          <UiTag tone="vein" size="sm">{{ subjectName(detail.subject_id) }}</UiTag>
          <span class="mono">{{ (detail.related_tags || []).length }} 个关联标签</span>
        </div>

        <div v-if="detail.summary" class="dblock">
          <span class="mono k">摘要</span>
          <p class="dtext">{{ detail.summary }}</p>
        </div>
        <UiEmpty v-else title="还没有摘要" hint="点卡片上的「AI 总结」生成" />

        <div class="dblock">
          <span class="mono k">关联错题</span>
          <UiEmpty v-if="linkedLoading" variant="skeleton" :rows="2" />
          <ul v-else-if="linked && linked.length" class="lnk">
            <li v-for="m in linked.slice(0, 12)" :key="m.id">
              <span class="mono lq">#{{ m.id }}</span
              >{{ m.question }}
            </li>
          </ul>
          <p v-else class="mono none">没有关联错题</p>
        </div>

        <div v-if="(detail.related_tags || []).length" class="dblock">
          <span class="mono k">关联标签</span>
          <div class="chips">
            <UiTag v-for="t in detail.related_tags" :key="t" tone="gold" size="sm">{{ t }}</UiTag>
          </div>
        </div>
      </div>
      <template #foot>
        <UiButton variant="quiet" @click="detailOpen = false">关闭</UiButton>
      </template>
    </UiModal>
  </main>
</template>

<style scoped>
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 28px);
}
.filters {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

/* 标签快捷条：一行可点的标签，带错题数 */
.tagbar {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  margin-bottom: clamp(16px, 3vh, 28px);
}
.tbtn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font-size: var(--fs-sm);
  color: var(--ink-1);
  transition:
    border-color 0.22s var(--e-settle),
    color 0.22s var(--e-settle),
    background 0.22s var(--e-settle);
}
.tbtn:hover {
  border-color: var(--vein);
  color: var(--ink-0);
}
.tbtn.on {
  border-color: var(--redshift);
  color: var(--ink-0);
  background: oklch(0.665 0.196 34 / 0.1);
}
.tbtn .n {
  color: var(--ink-3);
}

.wall {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
  gap: 14px;
}
.chead {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 9px;
}
.kname {
  font-size: var(--fs-h2);
  font-weight: 500;
  letter-spacing: -0.01em;
}
.subj {
  margin-left: auto;
  color: var(--ink-3);
}
.ksum {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  line-height: 1.75;
  min-height: 2.6em;
}
.ksum.none {
  color: var(--ink-3);
}
.cfoot {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin-top: 13px;
}
.sum {
  margin-left: auto;
}

.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: clamp(24px, 4vh, 44px);
}
.pnum {
  color: var(--ink-2);
}

/* 详情 */
.det {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dmeta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-2);
}
.dblock {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.k {
  color: var(--ink-3);
}
.dtext {
  line-height: 1.9;
  color: var(--ink-1);
  white-space: pre-wrap;
}
.lnk {
  list-style: none;
  display: grid;
  gap: 7px;
}
.lnk li {
  padding: 9px 12px;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  line-height: 1.65;
  font-size: var(--fs-sm);
}
.lq {
  margin-right: 8px;
  color: var(--ink-3);
}
.chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.none {
  color: var(--ink-3);
}

@media (max-width: 820px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
