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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

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
import EnglishPanel from '../components/EnglishPanel.vue'
import MathText from '../components/MathText.vue'

const PAGE_SIZE = 9 // 3×3：用户要求每页 9 题

const pageRoot = ref(null)
const loading = ref(true)
const errorText = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)

const filters = reactive({ search: '', subject_id: '', difficulty: '' })
const subjects = ref([])

const detailOpen = ref(false)
/** 灯箱当前显示的图片 URL（空串 = 关闭） */
const lightbox = ref('')
const lbEl = ref(null)
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

/**
 * 打开灯箱：**收起详情弹层**再显示灯箱。
 *
 * 为什么不是简单叠一层：灯箱视觉上在弹层之上（z-index 96 > 92），
 * 但 UiModal 的 Esc 监听绑在 document 捕获阶段并 stopPropagation()，
 * 会把 Esc 在到达灯箱之前截走 —— 视觉层级与事件流不一致。
 * 让它成为独立顶层视图后，Esc 只被当前顶层处理，行为可预期。
 */
function openLightbox(src) {
  lightbox.value = src
  detailOpen.value = false
  nextTick(() => lbEl.value?.focus?.())
}

/** 关灯箱：回到详情弹层（用户是从详情里点开图的，不能把他丢在空页面） */
function closeLightbox() {
  lightbox.value = ''
  if (detail.value) detailOpen.value = true
}

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

/**
 * 题图 URL。
 *
 * 踩过的坑：后端 `images` 里的值**自带 `images/` 前缀**（如 `images/xxx.png`），
 * 我又拼了一次 `/images/`，得到 `/images/images/xxx.png` - 404 - 用户看到裂图。
 * 所以必须先把已有的 `images/` 前缀剥掉。
 *
 * 列表用 `/images/thumb/<file>`（后端懒生成 WebP，实测 334KB - 33.8KB），
 * 详情用原图 —— 与 v2 的做法一致。
 */
function imageName(item) {
  const v = String(item || '').trim()
  if (!v) return ''
  if (v.startsWith('data:') || v.startsWith('http')) return v
  return v.replace(/^\/+/, '').replace(/^images\//, '')
}

function firstImage(row, { thumb = false } = {}) {
  const list = Array.isArray(row && row.images) ? row.images : []
  const first = list.find((x) => x && typeof x === 'string')
  if (!first) return ''
  if (first.startsWith('data:') || first.startsWith('http')) return first
  return `/images/${thumb ? 'thumb/' : ''}${imageName(first)}`
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
      <h1 class="mono page-h1">错题星表</h1>
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
          tilt
          @select="openDetail(row)"
        >
          <div class="chead">
            <UiTag :tone="typeTone(row.question_type)" size="sm">{{
              typeName(row.question_type)
            }}</UiTag>
            <span class="mono subj">{{ subjectName(row.subject_id) }}</span>
            <span v-if="row.source" class="mono src">{{ row.source }}</span>
          </div>
          <p class="q"><MathText :text="row.question" /></p>
          <!-- 题图：真题截图/公式图，没有就整块不出现（不留空框） -->
          <img
            v-if="firstImage(row)"
            class="shot"
            :src="firstImage(row, { thumb: true })"
            :alt="`第 ${row.id} 题的题目图像`"
            loading="lazy"
          />

          <div class="cfoot">
            <span class="diff" :aria-label="`难度 ${row.difficulty || 0} / 5`">
              <i
                v-for="n in 5"
                :key="n"
                :class="{ on: n <= (row.difficulty || 0) }"
                aria-hidden="true"
              ></i>
            </span>
            <InkDot :value="Math.round((row.mastery_level || 0) / 20)" label="掌握度" />
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

        <p class="dq"><MathText :text="detail.question" /></p>

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
            <span class="mono l">{{ String.fromCharCode(65 + i) }}</span>
            <MathText :text="text || '（空）'" />
          </li>
        </ul>

        <div v-if="detail.correct_answer" class="ansblock">
          <span class="mono k">标准答案</span>
          <p class="av"><MathText :text="detail.correct_answer" /></p>
        </div>

        <div v-if="detail.analysis" class="ansblock">
          <span class="mono k">解析</span>
          <p class="an"><MathText :text="detail.analysis" /></p>
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

        <!-- 英语题：中英对照 + 逐句拆解 + 短语/生词与词性（按 v2 的字段形状呈现） -->
        <!-- 详情里的题图用原图（列表用缩略图）；点图开灯箱 -->
        <button
          v-if="firstImage(detail)"
          class="shot-btn"
          type="button"
          aria-label="放大查看题目图像"
          @click="openLightbox(firstImage(detail))"
        >
          <img
            class="shot shot-full"
            :src="firstImage(detail)"
            :alt="`第 ${detail.id} 题的题目图像`"
          />
        </button>

        <EnglishPanel v-if="detail.passage_text" :data="detail" />

        <p class="mono dnote">编辑与复习入口在后续页面接入。</p>
      </div>
      <template #foot>
        <UiButton variant="quiet" @click="detailOpen = false">关闭</UiButton>
      </template>
    </UiModal>

    <!-- 灯箱：点题图放大；Esc 或点背景关闭 -->
    <Teleport to="body">
      <Transition name="lb">
        <div
          v-if="lightbox"
          ref="lbEl"
          class="lb"
          role="dialog"
          aria-modal="true"
          aria-label="题目图像放大"
          tabindex="-1"
          @click="closeLightbox"
          @keydown.esc.stop="closeLightbox"
        >
          <img :src="lightbox" alt="题目图像（放大）" />
          <span class="mono lb-hint">点任意处或按 Esc 关闭</span>
        </div>
      </Transition>
    </Teleport>
  </main>
</template>

<style scoped>
.page-h1 {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  font-weight: 400;
  letter-spacing: 0.12em;
  margin: 0;
}
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
  /* 长公式/长串必须断行，否则会把卡片撑破（用户截图里的溢出） */
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: var(--fs-h3, 1rem);
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.shot-full {
  max-height: none;
  margin: 4px 0 2px;
  object-fit: contain;
}

.shot {
  display: block;
  width: 100%;
  max-height: 132px;
  object-fit: cover;
  object-position: top;
  margin-top: 11px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-0);
}

/* 难度：五枚墨点式星条，不用字符星号（全站禁用字符图标） */
.diff {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}
.diff i {
  width: 11px;
  height: 3px;
  background: var(--sky-3);
  transition: background 0.3s var(--e-settle);
}
.diff i.on {
  background: var(--gold);
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
  overflow-wrap: anywhere;
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
  overflow-wrap: anywhere;
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
/* ── 题图按钮与灯箱 ─────────────────────────────────────────── */
.shot-btn {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  cursor: zoom-in;
  border-radius: var(--radius);
  overflow: hidden;
}
.shot-btn:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}
.shot-btn .shot {
  transition:
    transform 0.5s var(--e-settle),
    opacity 0.3s var(--e-settle);
}
.shot-btn:hover .shot {
  transform: scale(1.012);
  opacity: 0.94;
}

/* 灯箱：暗底上不用纯黑厚遮罩，用深蓝黑 + 轻模糊，保持"星图"气质 */
.lb {
  position: fixed;
  inset: 0;
  z-index: 96;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: clamp(20px, 5vh, 60px) var(--pad);
  background: oklch(0.145 0.018 265 / 0.9);
  backdrop-filter: blur(4px);
  cursor: zoom-out;
}
.lb img {
  max-width: min(96vw, 1400px);
  max-height: 82vh;
  object-fit: contain;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--sky-0);
}
.lb-hint {
  color: var(--ink-3);
}
.lb-enter-active,
.lb-leave-active {
  transition: opacity 0.28s var(--e-settle);
}
.lb-enter-active img,
.lb-leave-active img {
  transition: transform 0.38s var(--e-flare);
}
.lb-enter-from,
.lb-leave-to {
  opacity: 0;
}
.lb-enter-from img,
.lb-leave-to img {
  transform: scale(0.96);
}
@media (prefers-reduced-motion: reduce) {
  .lb-enter-active,
  .lb-leave-active,
  .lb-enter-active img,
  .lb-leave-active img,
  .shot-btn .shot {
    transition: none;
  }
}
</style>
