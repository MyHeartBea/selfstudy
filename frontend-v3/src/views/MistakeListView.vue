<!--
  MistakeListView —— 错题星表（列表 + 详情）
  ---------------------------------------------------------------------------
  契约要点（必须处理，否则会静默出错）：
    GET /api/mistakes **不传 page 返回数组；传 page 返回 { items, total, page, page_size }**。
    本页统一带 page（行为可预测），但**仍然兼容数组形状**——因为契约允许两种，
    而且 docs/contract-baseline.json 里两个形状都采样了。

  交互语义：错题 = 星；掌握度 = 墨点（记住多少）；复习遍数 = 星等（看过几遍）。
  设计取舍：整块可点靠事件绑在卡片本身（InkCard），卡片内控件一律 @click.stop。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import { usePageMotion } from '../design/usePageMotion'

import { baseApi, mistakesApi } from '../core/api'
import { toast } from '../ui/toast'
import InkCard from '../ui/InkCard.vue'
import InkDot from '../ui/InkDot.vue'
import StarRow from '../ui/StarRow.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'
import UiModal from '../ui/UiModal.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'

const PAGE_SIZE = 20

const pageRoot = ref(null)
const loading = ref(true)
const errorText = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)

const filters = reactive({ search: '', subject_id: '', difficulty: '' })
const subjects = ref([])

const detailOpen = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const subjectName = computed(
  () => (id) => subjects.value.find((s) => s.id === id)?.name || '未分科',
)

const DIFFICULTY = [
  { value: '', label: '全部难度' },
  { value: '1', label: '- 很轻松' },
  { value: '2', label: '-- 还行' },
  { value: '3', label: '--- 有点难' },
  { value: '4', label: '---- 很难' },
  { value: '5', label: '----- 完全不会' },
]

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const params = { page: page.value, page_size: PAGE_SIZE }
    if (filters.search.trim()) params.search = filters.search.trim()
    if (filters.subject_id) params.subject_id = Number(filters.subject_id)
    if (filters.difficulty) params.difficulty = Number(filters.difficulty)

    const data = await mistakesApi.list(params)
    // 双形状兼容：数组（无分页）或分页对象
    if (Array.isArray(data)) {
      items.value = data
      total.value = data.length
    } else {
      items.value = data?.items || []
      total.value = data?.total ?? items.value.length
    }
  } catch (e) {
    errorText.value = e?.message || '无法载入错题'
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadSubjects() {
  try {
    subjects.value = (await baseApi.subjects()) || []
  } catch {
    subjects.value = []
  }
}

const SUBJECT_OPTIONS = computed(() => [
  { value: '', label: '全部科目' },
  ...subjects.value.map((s) => ({ value: String(s.id), label: s.name })),
])

async function openDetail(row) {
  detailOpen.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await mistakesApi.detail(row.id)
  } catch (e) {
    toast.error(e?.message || '无法载入详情')
  } finally {
    detailLoading.value = false
  }
}

/** 题型中文名（与后端 question_type 枚举一致） */
function typeName(t) {
  return (
    { choice: '选择题', multi: '多选题', fill: '填空题', translation: '翻译', solution: '解答题' }[
      t
    ] || '题目'
  )
}
function typeTone(t) {
  return (
    { choice: 'vein', multi: 'violet', fill: 'gold', translation: 'vein', solution: 'gold' }[t] ||
    'ink'
  )
}

function applyFilters() {
  page.value = 1
  load()
}

let searchTimer = 0
watch(
  () => filters.search,
  () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(applyFilters, 320)
  },
)

onMounted(() => {
  loadSubjects()
  load()
})
onBeforeUnmount(() => clearTimeout(searchTimer))

/** 页面级动效：错峰入场 + 视差 + 磁吸 + 路径描绘（见 design/usePageMotion） */
usePageMotion(pageRoot, { stagger: 55 })
</script>

<template>
  <main ref="pageRoot" id="main" class="pad">
    <header class="head">
      <span class="mono">[02] INDEX · 错题星表</span>
      <span class="mono">{{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
    </header>

    <!-- 筛选条：整行可输入的搜索 + 两个下拉 -->
    <div class="filters reveal" data-reveal>
      <UiField
        v-model="filters.search"
        label="搜索"
        placeholder="题干 / 知识点 / 来源"
        @enter="applyFilters"
      />
      <UiSelect
        v-model="filters.subject_id"
        :options="SUBJECT_OPTIONS"
        label="科目"
        @change="applyFilters"
      />
      <UiSelect
        v-model="filters.difficulty"
        :options="DIFFICULTY"
        label="难度"
        @change="applyFilters"
      />
    </div>

    <UiEmpty v-if="loading" variant="skeleton" thumb :rows="3" />

    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action>
        <UiButton variant="solid" @click="load">重试</UiButton>
      </template>
    </UiEmpty>

    <UiEmpty
      v-else-if="!items.length"
      title="没有匹配的错题"
      hint="换个筛选条件，或者先去录入一道题"
    />

    <template v-else>
      <div class="grid reveal" data-reveal>
        <InkCard
          v-for="row in items"
          :key="row.id"
          :spine="row.correct_answer ? 'var(--ink-3)' : 'var(--redshift)'"
          :flagged="(row.wrong_count || 0) >= 3"
          @select="openDetail(row)"
        >
          <div class="chead">
            <UiTag :tone="typeTone(row.question_type)" size="sm">{{
              typeName(row.question_type)
            }}</UiTag>
            <span class="mono subj">{{ subjectName(row.subject_id) }}</span>
            <span v-if="row.source" class="mono src">{{ row.source }}</span>
          </div>
          <p class="q">{{ row.question }}</p>
          <div class="cfoot">
            <InkDot :value="Math.round((row.mastery || 0) / 20)" label="掌握度" />
            <StarRow :value="row.review_count || 0" :max="7" label="复习遍数" />
            <span class="mono cnt">错 {{ row.wrong_count || 0 }} 次</span>
          </div>
        </InkCard>
      </div>

      <div class="pager reveal" data-reveal>
        <UiButton :disabled="page <= 1" @click="((page -= 1), load())">上一页</UiButton>
        <span class="mono pnum">{{ page }} / {{ totalPages }}</span>
        <UiButton :disabled="page >= totalPages" @click="((page += 1), load())">下一页</UiButton>
      </div>
    </template>

    <!-- 详情：只读展示，编辑留到后续 -->
    <UiModal v-model="detailOpen" title="错题详情" size="lg">
      <UiEmpty v-if="detailLoading" variant="skeleton" :rows="4" />
      <UiEmpty v-else-if="!detail" title="没有取到详情" hint="可能是网络问题，或该题已被删除" />
      <div v-else class="det">
        <div class="dmeta">
          <UiTag :tone="typeTone(detail.question_type)" size="sm">{{
            typeName(detail.question_type)
          }}</UiTag>
          <UiTag tone="ink" size="sm">{{ subjectName(detail.subject_id) }}</UiTag>
          <span class="mono">难度 {{ detail.difficulty || '-' }}</span>
          <span class="mono">错 {{ detail.wrong_count || 0 }} 次</span>
        </div>

        <p class="dq">{{ detail.question }}</p>

        <ul v-if="detail.question_type === 'choice'" class="dopts">
          <li
            v-for="(text, i) in [
              detail.option_a,
              detail.option_b,
              detail.option_c,
              detail.option_d,
            ]"
            :key="i"
          >
            <span class="mono l">{{ String.fromCharCode(65 + i) }}</span
            >{{ text || '（空）' }}
          </li>
        </ul>

        <div v-if="detail.correct_answer" class="ansblock">
          <span class="mono k">标准答案</span>
          <p class="av">{{ detail.correct_answer }}</p>
        </div>

        <div v-if="detail.analysis" class="ansblock">
          <span class="mono k">解析</span>
          <p class="an">{{ detail.analysis }}</p>
        </div>

        <!-- 关联信息由行内标签呈现，不另起一堆卡片 -->
        <div v-if="detail.knowledge_extra || detail.related_knowledge?.length" class="rel">
          <span class="mono k">关联知识点</span>
          <div class="chips">
            <UiTag
              v-for="k in detail.related_knowledge || []"
              :key="k.id || k.tag_name"
              tone="vein"
              size="sm"
            >
              {{ k.tag_name || k }}
            </UiTag>
            <span v-if="!(detail.related_knowledge || []).length" class="mono none">无</span>
          </div>
        </div>

        <p class="mono dnote">编辑与复习入口在后续页面接入。</p>
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
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
  margin-bottom: clamp(16px, 3vh, 30px);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr));
  gap: 14px;
}
.chead {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 11px;
}
.subj {
  color: var(--ink-2);
}
.src {
  color: var(--ink-3);
  margin-left: auto;
}
.q {
  font-size: var(--fs-h3, 1rem);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.cfoot {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 13px;
  flex-wrap: wrap;
}
.cnt {
  margin-left: auto;
  color: var(--ink-3);
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
  flex-wrap: wrap;
  color: var(--ink-2);
}
.dq {
  font-size: var(--fs-h2);
  line-height: 1.7;
  font-weight: 500;
}
.dopts {
  list-style: none;
  display: grid;
  gap: 7px;
}
.dopts li {
  padding: 9px 12px;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  line-height: 1.65;
}
.dopts .l {
  margin-right: 8px;
  color: var(--ink-2);
}
.ansblock {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.k {
  color: var(--ink-3);
}
.av {
  font-size: var(--fs-h2);
  font-weight: 500;
  color: var(--redshift);
}
.an {
  line-height: 1.85;
  color: var(--ink-1);
}
.chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.none {
  color: var(--ink-3);
}
.dnote {
  color: var(--ink-3);
}

@media (max-width: 820px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
