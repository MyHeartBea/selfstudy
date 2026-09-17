<!--
  MistakeListView —— 错题星图（重铸版）
  ===========================================================================
  用户要求：审美基准是 Awwwards SOTD / FWA / CSS Design Awards 每日最佳，
  不是模板化 SaaS；并且要**物理感动效**（弹簧、惯性、阻尼、延迟、错峰）。
  这一版与"卡片网格"的本质区别（这是重铸的核心，不是换皮）：
    1. **入场用真弹簧积分**（src/design/physics.js），不是 CSS cubic-bezier：
       曲线到点即停，弹簧有速度、过冲、回弹。起始位移按列错峰，整屏像"落定"。
    2. **悬停：倾斜跟随指针（3°）+ 高光 sheen + 三层视差错幅位移**
       —— 悬停不是"背景变色"，而是这张卡"被拿起来看"。
    3. **难度五格墨条 + 掌握度墨线贴底边**：一眼可读"这道题我掌握了多少"。
    4. **题图在上 / 题干居中 / 元信息沉底**三层结构，悬停时各层位移幅度不同 - 厚度感。
    5. 题图点击进灯箱（独立顶层视图，Esc / 点背景关闭）。
  物理边界（诚实说明）：
    · 本页做**入场弹簧 + 悬停视差**；**拖拽排序与惯性滑行未做**——
      那需要后端的排序持久化接口，现在没有。不假装做了。
    · 全部只动 transform / opacity；reduced-motion 下直接落位。
  本轮同时**补齐此前缺失的功能**：暂停/恢复复习、删除错题（后端接口一直有，界面没做）。
-->
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ArrowUpRight, Pause, Play, Trash2, X } from 'lucide-vue-next'

import { baseApi, mistakesApi } from '../core/api'
import { springIn, stagger } from '../design/physics'
import { toast } from '../ui/toast'
import EnglishPanel from '../components/EnglishPanel.vue'
import InkDot from '../ui/InkDot.vue'
import MathText from '../components/MathText.vue'
import StarRow from '../ui/StarRow.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'
import UiModal from '../ui/UiModal.vue'
import UiTag from '../ui/UiTag.vue'

const PAGE_SIZE = 9 // 3×3 采样棋盘
const gridEl = ref(null)
let itemStops = []

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
const lightbox = ref('')
const lbEl = ref(null)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const subjectName = (id) => subjects.value.find((s) => s.id === id)?.name || '未分科'

const DIFFICULTY = [
  { value: '', label: '全部难度' },
  { value: '1', label: '- 很轻松' },
  { value: '2', label: '-- 还行' },
  { value: '3', label: '--- 有点难' },
  { value: '4', label: '---- 很难' },
  { value: '5', label: '----- 完全不会' },
]

/* ── 数据 ─────────────────────────────────────────────────── */
async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const params = { page: page.value, page_size: PAGE_SIZE }
    if (filters.search.trim()) params.search = filters.search.trim()
    if (filters.subject_id) params.subject_id = Number(filters.subject_id)
    if (filters.difficulty) params.difficulty = Number(filters.difficulty)

    const data = await mistakesApi.list(params)
    // 双形状兼容：不传 page 返回数组，传 page 返回分页对象
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
  await nextTick()
  runEntrance()
}

async function loadSubjects() {
  try {
    subjects.value = (await baseApi.subjects()) || []
  } catch {
    subjects.value = []
  }
}

/* ── 物理入场：真弹簧 + 按列错峰 ─────────────────────────── */
function runEntrance() {
  itemStops.forEach((fn) => fn())
  itemStops = []
  const root = gridEl.value
  if (!root) return
  const cards = Array.from(root.querySelectorAll('.tile'))
  if (!cards.length) return
  const startAt = stagger(cards.length, 58)
  cards.forEach((el, i) => {
    // 同一行内按列错峰，行与行之间再叠一层延迟 —— 落定感来自"不同时到达"
    const delay = startAt(i % 3) + Math.floor(i / 3) * 70
    itemStops.push(springIn(el, { delay, y: 34, preset: 'settle' }))
  })
}

/* ── 悬停视差：三层不同幅度（写 CSS 变量，避免与倾斜的内联 transform 打架）── */
function onTileMove(e) {
  const el = e.currentTarget
  if (!window.matchMedia('(pointer: fine)').matches) return
  const r = el.getBoundingClientRect()
  const px = (e.clientX - r.left) / r.width
  const py = (e.clientY - r.top) / r.height
  el.style.setProperty('--tilt-y', `${((px - 0.5) * 3).toFixed(2)}deg`)
  el.style.setProperty('--tilt-x', `${((0.5 - py) * 3).toFixed(2)}deg`)
  el.style.setProperty('--sheen-x', `${(px * 100).toFixed(1)}%`)
  el.style.setProperty('--sheen-y', `${(py * 100).toFixed(1)}%`)
  el.style.setProperty('--par-x', `${((px - 0.5) * 10).toFixed(1)}px`)
  el.style.setProperty('--par-y', `${((py - 0.5) * 8).toFixed(1)}px`)
}
function onTileLeave(e) {
  const el = e.currentTarget
  el.style.removeProperty('--tilt-x')
  el.style.removeProperty('--tilt-y')
  el.style.removeProperty('--par-x')
  el.style.removeProperty('--par-y')
  el.style.setProperty('--sheen-x', '50%')
  el.style.setProperty('--sheen-y', '50%')
}

/* ── 详情 ─────────────────────────────────────────────────── */
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

/**
 * 打开灯箱：**收起详情弹层**再显示灯箱。
 * 为什么：UiModal 的 Esc 监听绑在 document 捕获阶段并 stopPropagation()，
 * 灯箱若作为弹层内部子节点，视觉在上（z-index 96>92）但事件先被底层截走。
 * 让它成为独立顶层视图，视觉层级与事件流就一致了（已实测验证）。
 */
function openLightbox(src) {
  lightbox.value = src
  detailOpen.value = false
  nextTick(() => lbEl.value?.focus?.())
}
function closeLightbox() {
  lightbox.value = ''
  if (detail.value) detailOpen.value = true
}

/* ── 本轮补齐的功能：暂停/恢复、删除（后端接口一直有）──────── */
async function togglePause(row) {
  const next = !row.review_paused
  try {
    await mistakesApi.setPaused(row.id, next)
    row.review_paused = next
    toast.success(next ? '已暂停复习这道题' : '已恢复复习')
  } catch (e) {
    toast.error(e?.message || '操作失败')
  }
}

async function removeMistake(row) {
  if (!window.confirm('删除这道错题？该操作不可撤销。')) return
  try {
    await mistakesApi.remove(row.id)
    toast.success('已删除')
    detailOpen.value = false
    await load()
  } catch (e) {
    toast.error(e?.message || '删除失败')
  }
}

/* ── 工具 ─────────────────────────────────────────────────── */
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
function imageName(item) {
  const v = String(item || '').trim()
  if (!v) return ''
  if (v.startsWith('data:') || v.startsWith('http')) return v
  return v.replace(/^\/+/, '').replace(/^images\//, '')
}
/** 题图：后端 images 值自带 images/ 前缀，必须剥掉再拼；列表用缩略图通道 */
function firstImage(row, { thumb = false } = {}) {
  const list = Array.isArray(row?.images) ? row.images : []
  const first = list.find((x) => x && typeof x === 'string')
  if (!first) return ''
  if (first.startsWith('data:') || first.startsWith('http')) return first
  return `/images/${thumb ? 'thumb/' : ''}${imageName(first)}`
}
/** 掌握度 0-100 - 底部墨线宽度（本页最重要的"一眼可读"信息） */
function masteryPct(row) {
  return Math.max(0, Math.min(100, Math.round(row?.mastery_level ?? 0)))
}
function diffDots(row) {
  return Math.max(0, Math.min(5, Math.round(row?.difficulty ?? 0)))
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
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  itemStops.forEach((fn) => fn())
})
</script>

<template>
  <main id="main" class="pad">
    <header class="head">
      <h1 class="mono page-h1">错题星图</h1>
      <span class="mono">{{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
    </header>

    <div class="filters">
      <UiField
        v-model="filters.search"
        label="搜索"
        placeholder="题干 / 知识点 / 来源"
        @enter="applyFilters"
      />
      <div class="fsel">
        <label class="mono" for="f-subj">科目</label>
        <select id="f-subj" v-model="filters.subject_id" @change="applyFilters">
          <option value="">全部科目</option>
          <option v-for="s in subjects" :key="s.id" :value="String(s.id)">{{ s.name }}</option>
        </select>
      </div>
      <div class="fsel">
        <label class="mono" for="f-diff">难度</label>
        <select id="f-diff" v-model="filters.difficulty" @change="applyFilters">
          <option v-for="d in DIFFICULTY" :key="d.value" :value="d.value">{{ d.label }}</option>
        </select>
      </div>
    </div>

    <UiEmpty v-if="loading" variant="skeleton" thumb :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty
      v-else-if="!items.length"
      title="没有匹配的错题"
      hint="换个筛选条件，或者先去录入一道题"
    />

    <!-- 星图：3×3 采样棋盘 -->
    <div v-else ref="gridEl" class="chart">
      <article
        v-for="row in items"
        :key="row.id"
        class="tile"
        :class="{ flagged: (row.wrong_count || 0) >= 3, paused: row.review_paused }"
        tabindex="0"
        role="button"
        :aria-label="`打开第 ${row.id} 题详情`"
        @click="openDetail(row)"
        @keydown.enter.prevent="openDetail(row)"
        @pointermove="onTileMove"
        @pointerleave="onTileLeave"
      >
        <div class="layer shot-layer">
          <img
            v-if="firstImage(row, { thumb: true })"
            class="shot"
            :src="firstImage(row, { thumb: true })"
            :alt="`第 ${row.id} 题的题目图像`"
            loading="lazy"
          />
          <span v-else class="shot-empty mono" aria-hidden="true">无题图</span>
          <span class="sheen" aria-hidden="true"></span>
        </div>

        <div class="layer text-layer">
          <div class="tmeta">
            <UiTag :tone="typeTone(row.question_type)" size="sm">
              {{ typeName(row.question_type) }}
            </UiTag>
            <span class="mono subj">{{ subjectName(row.subject_id) }}</span>
            <span class="mono src">{{ row.source_name || row.source || '未标注' }}</span>
          </div>
          <p class="q"><MathText :text="row.question" /></p>
        </div>

        <div class="layer meta-layer">
          <span class="dots" :aria-label="`难度 ${diffDots(row)} / 5`">
            <i v-for="n in 5" :key="n" :class="{ on: n <= diffDots(row) }" aria-hidden="true"></i>
          </span>
          <InkDot :value="Math.round(masteryPct(row) / 20)" label="掌握度" />
          <StarRow :value="row.review_count || 0" :max="7" label="复习遍数" />
          <span class="mono cnt">错 {{ row.wrong_count || 0 }} 次</span>
          <ArrowUpRight class="arw" :size="17" aria-hidden="true" />
        </div>

        <span class="mastery" :style="{ width: masteryPct(row) + '%' }" aria-hidden="true"></span>
        <span v-if="row.review_paused" class="paused-flag mono">已暂停</span>
      </article>
    </div>

    <div v-if="totalPages > 1" class="pager">
      <UiButton :disabled="page <= 1" @click="((page -= 1), load())">上一页</UiButton>
      <span class="mono pnum">{{ page }} / {{ totalPages }}</span>
      <UiButton :disabled="page >= totalPages" @click="((page += 1), load())">下一页</UiButton>
    </div>

    <UiModal v-model="detailOpen" title="错题详情" size="lg">
      <UiEmpty v-if="detailLoading" variant="skeleton" :rows="4" />
      <UiEmpty v-else-if="!detail" title="没有取到详情" hint="可能是网络问题，或该题已被删除" />
      <div v-else class="det">
        <div class="dmeta">
          <UiTag :tone="typeTone(detail.question_type)" size="sm">
            {{ typeName(detail.question_type) }}
          </UiTag>
          <UiTag tone="ink" size="sm">{{ subjectName(detail.subject_id) }}</UiTag>
          <span class="mono">难度 {{ detail.difficulty || '-' }}</span>
          <span class="mono">错 {{ detail.wrong_count || 0 }} 次</span>
          <span v-if="detail.review_paused" class="mono warn">已暂停复习</span>
        </div>

        <button
          v-if="firstImage(detail)"
          class="shot-btn"
          type="button"
          aria-label="放大查看题目图像"
          @click="openLightbox(firstImage(detail))"
        >
          <img class="shot shot-full" :src="firstImage(detail)" :alt="`第 ${detail.id} 题图像`" />
        </button>

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

        <EnglishPanel v-if="detail.passage_text" :data="detail" />

        <div v-if="(detail.related_knowledge || []).length" class="rel">
          <span class="mono k">关联知识点</span>
          <div class="chips">
            <UiTag
              v-for="k in detail.related_knowledge"
              :key="k.id || k.tag_name"
              tone="vein"
              size="sm"
            >
              {{ k.tag_name || k }}
            </UiTag>
          </div>
        </div>
      </div>

      <template #foot>
        <!-- 本轮补齐：暂停/恢复复习、删除（后端接口一直有，此前界面没有入口） -->
        <UiButton v-if="detail" variant="quiet" @click="togglePause(detail)">
          <Pause v-if="!detail.review_paused" :size="14" aria-hidden="true" />
          <Play v-else :size="14" aria-hidden="true" />
          {{ detail.review_paused ? '恢复复习' : '暂停复习' }}
        </UiButton>
        <UiButton v-if="detail" variant="danger" @click="removeMistake(detail)">
          <Trash2 :size="14" aria-hidden="true" />删除
        </UiButton>
        <UiButton variant="solid" @click="detailOpen = false">关闭</UiButton>
      </template>
    </UiModal>

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
          <span class="lb-x" aria-hidden="true"><X :size="18" /></span>
        </div>
      </Transition>
    </Teleport>
  </main>
</template>

<style scoped>
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: 1520px;
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
}
.page-h1 {
  font-family: var(--font-mono);
  font-size: var(--fs-mono);
  font-weight: 400;
  letter-spacing: 0.12em;
  margin: 0;
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 28px);
  flex-wrap: wrap;
}

.filters {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 0.9fr) minmax(0, 0.9fr);
  gap: 14px;
  margin-bottom: clamp(16px, 3vh, 30px);
}
.fsel {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.fsel label {
  color: var(--ink-2);
}
.fsel select {
  width: 100%;
  padding: 11px 12px;
  background: var(--sky-1);
  color: var(--ink-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  font: inherit;
  font-size: var(--fs-body);
}
.fsel select:focus {
  outline: none;
  border-color: var(--redshift);
}

/* ── 星图棋盘 ─────────────────────────────────────────────── */
.chart {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(10px, 1.4vw, 20px);
}
.tile {
  position: relative;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
  padding: 14px 15px 16px;
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  isolation: isolate;
  overflow: hidden;
  /* 倾斜由 CSS 变量驱动（JS 逐帧写变量，而不是写内联 transform，避免互相覆盖） */
  transform: perspective(900px) rotateX(var(--tilt-x, 0deg)) rotateY(var(--tilt-y, 0deg))
    translateY(var(--lift, 0px));
  transition:
    transform 0.18s linear,
    border-color 0.35s var(--e-settle),
    background 0.35s var(--e-settle);
  will-change: transform;
}
.tile:hover,
.tile:focus-visible {
  --lift: -4px;
  background: var(--sky-2);
  border-color: var(--line-strong);
  box-shadow: 0 22px 48px -30px #000000e6;
}
.tile:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}
.sheen {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
  background: radial-gradient(
    300px circle at var(--sheen-x, 50%) var(--sheen-y, 50%),
    oklch(0.945 0.014 265 / 0.12),
    transparent 60%
  );
  transition: opacity 0.32s var(--e-settle);
}
.tile:hover .sheen {
  opacity: 1;
}
/* 三层视差：位移幅度不同 - "卡片有厚度" */
.layer {
  position: relative;
  z-index: 1;
  transition: transform 0.32s var(--e-settle);
}
.tile:hover .shot-layer {
  transform: translate3d(calc(var(--par-x, 0px) * 1.6), calc(var(--par-y, 0px) * 1.6), 0);
}
.tile:hover .text-layer {
  transform: translate3d(var(--par-x, 0px), var(--par-y, 0px), 0);
}
.tile:hover .meta-layer {
  transform: translate3d(calc(var(--par-x, 0px) * 0.5), calc(var(--par-y, 0px) * 0.5), 0);
}

.shot-layer {
  position: relative;
  height: clamp(88px, 11vh, 132px);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-0);
  overflow: hidden;
}
.shot {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  display: block;
}
.shot-empty {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--ink-3);
}

.tmeta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 9px;
}
.subj {
  color: var(--ink-2);
}
.src {
  margin-left: auto;
  color: var(--ink-3);
}
.q {
  font-size: clamp(0.92rem, 1.1vw, 1.05rem);
  line-height: 1.7;
  color: var(--ink-0);
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meta-layer {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--ink-3);
}
.dots {
  display: inline-flex;
  gap: 3px;
}
.dots i {
  width: 11px;
  height: 3px;
  background: var(--sky-3);
}
.dots i.on {
  background: var(--gold);
}
.meta-layer .cnt {
  margin-left: auto;
}
.arw {
  color: var(--ink-3);
  transition:
    color 0.28s var(--e-settle),
    transform 0.42s var(--e-flare);
}
.tile:hover .arw {
  color: var(--redshift);
  transform: translate(3px, -3px);
}

.mastery {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--vein), var(--ink-0));
  transition: width 0.7s var(--e-settle);
  z-index: 2;
}
.tile.flagged {
  border-color: oklch(0.665 0.196 34 / 0.5);
}
.tile.paused {
  opacity: 0.55;
}
.paused-flag {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 3;
  padding: 2px 7px;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  background: var(--sky-0);
  color: var(--gold);
  font-size: 10px;
  letter-spacing: 0.12em;
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

/* ── 详情 ─────────────────────────────────────────────────── */
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
.dmeta .warn {
  color: var(--gold);
}
.dq {
  font-size: var(--fs-h2);
  line-height: 1.7;
  font-weight: 500;
  overflow-wrap: anywhere;
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
  overflow-wrap: anywhere;
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
.rel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}

/* ── 题图与灯箱 ───────────────────────────────────────────── */
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
.shot-full {
  max-height: none;
  margin: 4px 0 2px;
  object-fit: contain;
  background: var(--sky-0);
  transition: opacity 0.3s var(--e-settle);
}
.shot-btn:hover .shot-full {
  opacity: 0.94;
}
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
.lb-x {
  position: absolute;
  top: var(--pad);
  right: var(--pad);
  color: var(--ink-2);
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

@media (max-width: 1100px) {
  .chart {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filters {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 760px) {
  .chart {
    grid-template-columns: 1fr;
  }
  .filters {
    grid-template-columns: 1fr;
  }
  /* 触屏不照搬桌面倾斜：只用位移与高光 */
  .tile {
    transform: none;
  }
  .tile:hover .shot-layer,
  .tile:hover .text-layer,
  .tile:hover .meta-layer {
    transform: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .tile,
  .layer,
  .sheen,
  .arw,
  .mastery,
  .shot-full,
  .lb-enter-active,
  .lb-leave-active,
  .lb-enter-active img,
  .lb-leave-active img {
    transition: none;
  }
}
</style>
