<script setup>
/**
 * 生词本（英语二核心）：词表管理 + 闪卡快刷 + 批量导入。
 * 复习节奏：认识则阶梯拉远（1/2/4/7/15/30/60 天），模糊说明天，不认识留在队列。
 */
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import { speakEnglish, speechSupported } from '../utils/speech'
import { useCountUp } from '../utils/useCountUp'
import { formatTime } from '../composables/useBaseData'
import { useResourceList } from '../composables/useResourceList'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import FlipCard from '../ui/FlipCard.vue'
import YearRing from '../ui/YearRing.vue'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiLoadError from '../ui/UiLoadError.vue'
import UiModal from '../ui/UiModal.vue'
import UiPagination from '../ui/UiPagination.vue'
import Icon from '../ui/Icon.vue'

const route = useRoute()
const router = useRouter()
const mode = ref('list') // list | flashcard
const stats = ref({ total: 0, due: 0, mastered: 0, distribution: [] })
const nTotal = useCountUp(computed(() => stats.value.total))
const nDue = useCountUp(computed(() => stats.value.due))
const nMastered = useCountUp(computed(() => stats.value.mastered))

// —— 词表 ——
const page = ref(1)
const pageSize = ref(15)
const filters = reactive({
  // 命令面板跳回来时带 ?search=，得真的把它当筛选初始值（否则落在整本词表上）
  search: route.query.search ? String(route.query.search) : '',
  mastery: null,
  kind: '',
  sort: 'created_desc',
})

const {
  items,
  total,
  loading,
  loadError,
  load: loadList,
} = useResourceList(async () => {
  const params = { page: page.value, page_size: pageSize.value, sort: filters.sort }
  if (filters.search.trim()) params.search = filters.search.trim()
  if (filters.mastery !== null) params.mastery = filters.mastery
  if (filters.kind) params.kind = filters.kind
  const res = await request.get('/vocab', { params })
  return res.data.data
})

// —— 生词详情（整卡可点打开）——
const detailVisible = ref(false)
const detailRow = ref(null)

function openVocabDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

/** 详情转编辑：先关详情再开编辑（两层弹窗可叠，但串行更干净） */
function editFromDetail(row) {
  if (!row) return
  detailVisible.value = false
  openEdit(row)
}

/** 详情转删除：确认后关详情再删 */
async function removeFromDetail(row) {
  if (!row) return
  detailVisible.value = false
  await remove(row)
}

async function loadStats() {
  try {
    const res = await request.get('/vocab/stats')
    stats.value = res.data.data
  } catch (err) {}
}

function searchList() {
  page.value = 1
  loadList()
}

/** 切换「全部/单词/词语」分类并重新检索（模板里不要写多语句内联表达式，
 *  Prettier 会把它们拆行导致 Vue 编译失败）。 */
function selectKind(kind) {
  filters.kind = kind
  searchList()
}

let searchTimer = null
function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(searchList, 300)
}

onUnmounted(() => {
  // 组件卸载后不再触发搜索请求，避免定时器泄漏
  if (searchTimer) clearTimeout(searchTimer)
})

// —— 新增/编辑 ——
const editVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({ word: '', meaning: '', phonetic: '', example: '', note: '', source: '' })

function openCreate() {
  editingId.value = null
  Object.assign(form, { word: '', meaning: '', phonetic: '', example: '', note: '', source: '' })
  editVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    word: row.word,
    meaning: row.meaning,
    phonetic: row.phonetic,
    example: row.example,
    note: row.note,
    source: row.source,
  })
  editVisible.value = true
}

async function save() {
  if (!form.word.trim()) {
    toast.warning('请填写单词')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await request.put(`/vocab/${editingId.value}`, { ...form })
      toast.success('生词已更新')
    } else {
      await request.post('/vocab', { ...form })
      toast.success('生词已添加')
    }
    editVisible.value = false
    loadList()
    loadStats()
  } catch (err) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  const okFlag = await confirmDialog({
    title: '删除确认',
    message: `确定删除“${row.word}”吗？`,
    danger: true,
    confirmText: '删除',
  })
  if (!okFlag) return
  try {
    await request.delete(`/vocab/${row.id}`)
    toast.success('已删除')
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    loadList()
    loadStats()
  } catch (err) {}
}

// —— 批量导入 ——
const importVisible = ref(false)
const importSource = ref('')
const importText = ref('')
const importing = ref(false)

const importPreview = computed(
  () =>
    importText.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean).length,
)

function openImport() {
  importText.value = ''
  importSource.value = ''
  importVisible.value = true
}

async function doImport() {
  const lines = importText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  if (!lines.length) {
    toast.warning('请先粘贴生词')
    return
  }
  importing.value = true
  try {
    const res = await request.post('/vocab/import', { lines, source: importSource.value })
    const result = res.data.data
    toast.success(
      `导入完成：新增 ${result.created} 条${result.updated ? `，补充 ${result.updated} 条` : ''}${result.failed.length ? `，失败 ${result.failed.length} 条` : ''}`,
    )
    importVisible.value = false
    loadList()
    loadStats()
  } catch (err) {
  } finally {
    importing.value = false
  }
}

// —— 闪卡快刷 ——
const queue = ref([])
const cardIndex = ref(0)
const flipped = ref(false)
const sessionDone = ref(false)
const sessionCount = ref({ known: 0, fuzzy: 0, unknown: 0 })

// —— 三向滑动判分（F1）：右=认识 / 左=不认识 / 下=模糊 ——
// 指针事件覆盖鼠标与触屏；拖拽跟手（transform 直写），松手过阈值飞出判分、
// 否则回弹。键盘 左/右/下 方向键等价（onKeydown 内）。click 与拖拽用 justDragged 区分。
const drag = reactive({ dx: 0, dy: 0, active: false, moved: false })
let dragStart = null
let justDragged = false
const flyDir = ref(null) // 'known' | 'unknown' | 'fuzzy' 飞出中

const THRESHOLD = 80

function onCardPointerDown(e) {
  if (sessionDone.value || flyDir.value || !currentCard.value) return
  dragStart = { x: e.clientX, y: e.clientY }
  drag.active = true
  drag.moved = false
  drag.dx = 0
  drag.dy = 0
}

function onCardPointerMove(e) {
  if (!dragStart) return
  drag.dx = e.clientX - dragStart.x
  drag.dy = e.clientY - dragStart.y
  if (Math.hypot(drag.dx, drag.dy) > 8) drag.moved = true
}

function onCardPointerUp() {
  if (!dragStart) return
  dragStart = null
  drag.active = false
  const { dx, dy } = drag
  if (Math.abs(dx) >= THRESHOLD || dy >= THRESHOLD) {
    justDragged = true
    const result = dx >= THRESHOLD ? 'known' : dx <= -THRESHOLD ? 'unknown' : 'fuzzy'
    flyDir.value = result
    setTimeout(() => {
      flyDir.value = null
      drag.dx = 0
      drag.dy = 0
      drag.moved = false
      grade(result)
    }, 240)
  } else {
    drag.dx = 0
    drag.dy = 0
    drag.moved = false
  }
}

function onFlip() {
  // 拖拽结束后的 click 不当作翻面
  if (justDragged) {
    justDragged = false
    return
  }
  flipped.value = !flipped.value
}

// 拖拽跟手 + 飞出：样式直算（transform/opacity，不触发布局）
const cardDragStyle = computed(() => {
  if (flyDir.value === 'known')
    return { transform: 'translate(560px, -40px) rotate(12deg)', opacity: 0 }
  if (flyDir.value === 'unknown')
    return { transform: 'translate(-560px, -40px) rotate(-12deg)', opacity: 0 }
  if (flyDir.value === 'fuzzy') return { transform: 'translateY(420px)', opacity: 0 }
  return {
    transform: `translate(${drag.dx}px, ${drag.dy}px) rotate(${(drag.dx * 0.05).toFixed(2)}deg)`,
    transition: drag.active
      ? 'none'
      : 'transform 0.3s var(--ease-move), opacity 0.3s var(--ease-move)',
  }
})

const swipeVerdict = computed(() => {
  if (flyDir.value === 'known' || drag.dx >= THRESHOLD)
    return { label: '认识', cls: 'is-known', show: true }
  if (flyDir.value === 'unknown' || drag.dx <= -THRESHOLD)
    return { label: '不认识', cls: 'is-unknown', show: true }
  if (flyDir.value === 'fuzzy' || drag.dy >= THRESHOLD)
    return { label: '模糊', cls: 'is-fuzzy', show: true }
  return { label: '', cls: '', show: false }
})

const swipeHintStyle = computed(() => ({
  opacity: swipeVerdict.value.show
    ? Math.min(1, (Math.max(Math.abs(drag.dx), Math.max(drag.dy, 0)) - 30) / 50)
    : 0,
}))

async function startFlashcards() {
  try {
    const res = await request.get('/vocab/due', { params: { limit: 30 } })
    queue.value = res.data.data || []
    if (!queue.value.length) {
      toast.success('今天没有到期的生词，去添加新词或直接浏览词表')
      return
    }
    mode.value = 'flashcard'
    cardIndex.value = 0
    flipped.value = false
    sessionDone.value = false
    sessionCount.value = { known: 0, fuzzy: 0, unknown: 0 }
  } catch (err) {}
}

const currentCard = computed(() => queue.value[cardIndex.value] || null)

// —— 闪卡发音（浏览器本地 TTS）+ 真题语境回链 ——
const canSpeak = speechSupported()
function speakCard(card) {
  if (!card) return
  if (!speakEnglish(card.word)) toast.warning('当前浏览器不支持语音朗读')
}

const ctxHits = ref([])
const ctxLoading = ref(false)
const ctxCache = new Map() // vocab_id 到命中列表的会话内缓存，翻回来看不再请求

watch(
  () => [flipped.value, cardIndex.value],
  async ([isFlipped]) => {
    const card = currentCard.value
    if (!isFlipped || !card) return
    if (ctxCache.has(card.id)) {
      ctxHits.value = ctxCache.get(card.id)
      return
    }
    ctxLoading.value = true
    ctxHits.value = []
    try {
      const res = await request.get(`/vocab/${card.id}/context`, { silent: true })
      const hits = res.data.data || []
      ctxCache.set(card.id, hits)
      // 等待期间可能已翻到下一张，别把旧词的语境挂错卡
      if (currentCard.value && currentCard.value.id === card.id) ctxHits.value = hits
    } catch (err) {
      /* 语境是锦上添花，失败静默 */
    } finally {
      ctxLoading.value = false
    }
  },
)

/** 语境条目跳单题直练（与知识点详情「练这题」同一落点） */
function goContext(hit) {
  router.push({ path: '/review', query: { mode: 'curve', count: 1, mistake_id: hit.mistake_id } })
}

async function grade(result) {
  if (!currentCard.value) return
  try {
    await request.post(`/vocab/${currentCard.value.id}/review`, { result })
  } catch (err) {}
  sessionCount.value[result] += 1
  // 不认识的词立即排到队尾，直到全会
  if (result === 'unknown') {
    queue.value.push(currentCard.value)
  }
  flipped.value = false
  ctxHits.value = []
  ctxLoading.value = false
  if (cardIndex.value + 1 >= queue.value.length) {
    sessionDone.value = true
    loadStats()
    loadList()
  } else {
    cardIndex.value += 1
  }
}

const MASTERY_LABELS = ['生词', 'L1', 'L2', 'L3', 'L4', '已掌握', '已掌握', '已掌握', '已掌握']

function masteryLabel(level) {
  return MASTERY_LABELS[level] || `L${level}`
}

onMounted(() => {
  loadList()
  loadStats()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => window.removeEventListener('keydown', onKeydown))

// 闪卡键盘流：空格翻面，1/2/3 = 不认识/模糊/认识
function onKeydown(event) {
  if (mode.value !== 'flashcard' || sessionDone.value) return
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  if (event.key === ' ') {
    event.preventDefault()
    flipped.value = !flipped.value
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    flyGrade('known')
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    flyGrade('unknown')
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    flyGrade('fuzzy')
  } else if (flipped.value && event.key === '1') {
    grade('unknown')
  } else if (flipped.value && event.key === '2') {
    grade('fuzzy')
  } else if (flipped.value && event.key === '3') {
    grade('known')
  }
}

// 方向键 / 滑动共用的飞出判分（flyDir 驱动卡片飞出动画，落地后真正 grade）
function flyGrade(result) {
  if (flyDir.value || sessionDone.value || !currentCard.value) return
  flyDir.value = result
  setTimeout(() => {
    flyDir.value = null
    drag.dx = 0
    drag.dy = 0
    drag.moved = false
    grade(result)
  }, 240)
}

// —— Anki 卡组导出（TSV：单词/释义+例句/标签） ——
const exportingAnki = ref(false)

async function exportAnki() {
  exportingAnki.value = true
  try {
    const res = await request.get('/export/anki', { params: { type: 'vocab' } })
    const blob = new Blob([res.data], { type: 'text/tab-separated-values;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `生词本_anki_${new Date().toISOString().slice(0, 10)}.tsv`
    link.click()
    URL.revokeObjectURL(url)
    toast.success('已导出 Anki TSV，在 Anki 中「文件 > 导入」即可')
  } catch (err) {
    toast.error('Anki 导出失败')
  } finally {
    exportingAnki.value = false
  }
}
</script>

<template>
  <div class="page km-editorial">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Vocabulary</div>
        <h2>生词本</h2>
        <p class="view-desc">英语二的每日必修：滚动快刷生词，认识就拉远，不认识今天再见。</p>
      </div>
      <div class="header-actions">
        <UiButton variant="primary" @click="startFlashcards">
          <Icon name="layers" :size="15" />
          开始快刷（{{ stats.due }} 张到期）
        </UiButton>
        <UiButton variant="outline" @click="openImport">
          <Icon name="upload" :size="15" />
          批量导入
        </UiButton>
        <UiButton variant="outline" @click="openCreate">
          <Icon name="plus-circle" :size="15" />
          添加生词
        </UiButton>
        <UiButton variant="outline" :loading="exportingAnki" @click="exportAnki">
          <Icon name="download" :size="15" />
          Anki 卡组
        </UiButton>
      </div>
    </div>

    <div class="stats-strip">
      <div class="strip-item card" v-reveal>
        <span class="strip-icon"><Icon name="book" :size="17" /></span>
        <div>
          <div class="strip-num">{{ nTotal }}</div>
          <div class="strip-label">生词总数</div>
        </div>
      </div>
      <div class="strip-item card" v-reveal="50">
        <span class="strip-icon" style="color: var(--gold)"><Icon name="clock" :size="17" /></span>
        <div>
          <div class="strip-num">{{ nDue }}</div>
          <div class="strip-label">今日到期</div>
        </div>
      </div>
      <div class="strip-item card" v-reveal="100">
        <span class="strip-icon" style="color: var(--green)"><Icon name="check" :size="17" /></span>
        <div>
          <div class="strip-num">{{ nMastered }}</div>
          <div class="strip-label">已掌握</div>
        </div>
      </div>
      <div class="strip-item card dist" v-reveal="150">
        <div class="dist-bars">
          <div
            v-for="d in stats.distribution"
            :key="d.mastery"
            class="dist-col"
            :title="`${masteryLabel(d.mastery)}：${d.count} 词`"
          >
            <div
              class="dist-bar"
              :style="{
                height:
                  Math.max(
                    6,
                    (d.count / Math.max(1, Math.max(...stats.distribution.map((x) => x.count)))) *
                      40,
                  ) + 'px',
              }"
            ></div>
            <span class="dist-level">{{
              d.mastery === 0 ? '新' : d.mastery >= 5 ? '熟' : d.mastery
            }}</span>
          </div>
        </div>
        <span class="count-tip">掌握度分布</span>
      </div>
    </div>

    <!-- 闪卡模式 -->
    <div v-if="mode === 'flashcard'" class="flash-zone card card-pad">
      <template v-if="sessionDone">
        <div class="flash-done">
          <YearRing
            :total="sessionCount.known + sessionCount.fuzzy + sessionCount.unknown"
            :wrong="sessionCount.unknown"
            :size="170"
          />
          <h3>本轮快刷完成</h3>
          <p class="done-sub">
            认识 <b class="ok">{{ sessionCount.known }}</b> · 模糊
            <b class="warn">{{ sessionCount.fuzzy }}</b> · 不认识
            <b class="bad">{{ sessionCount.unknown }}</b>
          </p>
          <div class="done-actions">
            <UiButton variant="outline" @click="startFlashcards">再来一轮</UiButton>
            <UiButton variant="ghost" @click="mode = 'list'">返回词表</UiButton>
          </div>
        </div>
      </template>
      <template v-else-if="currentCard">
        <div class="flash-head">
          <span class="count-tip">{{ cardIndex + 1 }} / {{ queue.length }}</span>
          <UiTag size="sm" :color="currentCard.mastery_level >= 5 ? 'var(--green)' : 'var(--gold)'">
            {{ masteryLabel(currentCard.mastery_level) }}
          </UiTag>
          <UiButton size="sm" variant="ghost" @click="mode = 'list'">退出</UiButton>
        </div>
        <div class="flash-dragzone">
          <!-- 拖拽判分提示：右=认识（朱砂）/ 左=不认识（淡墨）/ 下=模糊 -->
          <span class="swipe-hint" :class="swipeVerdict.cls" :style="swipeHintStyle">{{
            swipeVerdict.label
          }}</span>
          <div :key="cardIndex" class="flash-swap" :style="cardDragStyle">
            <FlipCard
              :flipped="flipped"
              class="flash-stage"
              @flip="onFlip"
              @pointerdown="onCardPointerDown"
              @pointermove="onCardPointerMove"
              @pointerup="onCardPointerUp"
              @pointercancel="onCardPointerUp"
            >
              <template #front>
                <div class="flash-word-row">
                  <div class="flash-word serif">{{ currentCard.word }}</div>
                  <button
                    v-if="canSpeak"
                    type="button"
                    class="flash-speak"
                    title="朗读单词"
                    aria-label="朗读单词"
                    @click.stop="speakCard(currentCard)"
                  >
                    <Icon name="volume" :size="19" />
                  </button>
                </div>
                <div v-if="currentCard.phonetic" class="flash-phonetic">
                  {{ currentCard.phonetic }}
                </div>
                <span class="flash-tip">点击或空格翻面 · 右滑认识 / 左滑不认识 / 下滑模糊</span>
              </template>
              <template #back>
                <p class="flash-meaning">{{ currentCard.meaning || '（未填写释义）' }}</p>
                <p v-if="currentCard.example" class="flash-example">{{ currentCard.example }}</p>
                <p v-if="currentCard.note" class="flash-note">{{ currentCard.note }}</p>
                <div v-if="ctxHits.length" class="flash-ctx">
                  <span class="flash-ctx-label">真题里见过它</span>
                  <button
                    v-for="h in ctxHits"
                    :key="h.mistake_id"
                    type="button"
                    class="flash-ctx-item"
                    @click.stop="goContext(h)"
                  >
                    <span class="flash-ctx-src">{{
                      h.source_name || (h.source_year ? `${h.source_year} 真题` : '错题原文')
                    }}</span>
                    <span class="flash-ctx-snippet">{{ h.snippet }}</span>
                  </button>
                </div>
                <span v-else-if="ctxLoading" class="flash-ctx-label dim">找真题语境中…</span>
              </template>
            </FlipCard>
          </div>
        </div>
        <div class="grade-row" :class="{ disabled: !flipped }">
          <button
            type="button"
            class="grade-btn unknown"
            :disabled="!flipped"
            @click="grade('unknown')"
          >
            <Icon name="x" :size="17" />
            不认识
            <kbd>1</kbd>
          </button>
          <button
            type="button"
            class="grade-btn fuzzy"
            :disabled="!flipped"
            @click="grade('fuzzy')"
          >
            <Icon name="refresh" :size="17" />
            模糊
            <kbd>2</kbd>
          </button>
          <button
            type="button"
            class="grade-btn known"
            :disabled="!flipped"
            @click="grade('known')"
          >
            <Icon name="check" :size="17" />
            认识
            <kbd>3</kbd>
          </button>
        </div>
      </template>
    </div>

    <!-- 词表 -->
    <template v-else>
      <div class="card card-pad filter-bar">
        <div class="kind-tabs">
          <button
            v-for="k in [
              ['', '全部'],
              ['word', '单词'],
              ['phrase', '词语'],
            ]"
            :key="k[0]"
            class="kind-tab"
            :class="{ active: filters.kind === k[0] }"
            @click="selectKind(k[0])"
          >
            {{ k[1] }}
          </button>
        </div>
        <div class="filter-search">
          <Icon name="search" :size="15" class="search-icon" />
          <input
            v-model="filters.search"
            class="field-input"
            placeholder="搜索单词/释义/笔记"
            @keyup.enter="searchList"
            @input="debouncedSearch"
          />
        </div>
        <UiSelect
          v-model="filters.mastery"
          :options="
            ['生词', 'L1', 'L2', 'L3', 'L4', '已掌握'].map((label, i) => ({ label, value: i }))
          "
          placeholder="全部掌握度"
          clearable
          compact
          @change="searchList"
        />
        <UiSelect
          v-model="filters.sort"
          :options="[
            { label: '最新添加', value: 'created_desc' },
            { label: '最早添加', value: 'created_asc' },
            { label: '最不熟优先', value: 'mastery_asc' },
            { label: '按字母', value: 'alpha' },
          ]"
          compact
          @change="searchList"
        />
        <span class="count-tip">共 {{ total }} 词</span>
      </div>

      <UiLoadError v-if="loadError" text="生词本加载失败" @retry="loadList" />
      <UiEmpty
        v-else-if="!items.length && !loading"
        seal="词"
        text="生词本还是空的，粘贴词表批量导入或逐个添加"
        icon="book"
      />
      <div v-else class="vocab-grid km-list">
        <article
          v-for="(row, i) in items"
          :key="row.id"
          class="vocab-card km-card card"
          role="button"
          tabindex="0"
          :aria-label="`查看生词 ${row.word}`"
          :style="{ '--enter-delay': `calc(${Math.min(i, 11)} * var(--stagger-1))` }"
          @click="openVocabDetail(row)"
          @keydown.enter.prevent="openVocabDetail(row)"
          @keydown.space.prevent="openVocabDetail(row)"
        >
          <span class="v-mark serif" aria-hidden="true">{{
            (row.word || 'A').slice(0, 1).toUpperCase()
          }}</span>
          <div class="vocab-head">
            <span class="vocab-word serif">{{ row.word }}</span>
            <span v-if="row.kind === 'phrase'" class="vocab-kind">词语</span>
            <span
              class="m-dots"
              :title="masteryLabel(row.mastery_level)"
              :class="{ mastered: row.mastery_level >= 5 }"
            >
              <i v-for="d in 5" :key="d" :class="{ on: d <= row.mastery_level }"></i>
            </span>
          </div>
          <p class="vocab-meaning">{{ row.meaning || '—' }}</p>
          <p v-if="row.example" class="vocab-example">{{ row.example }}</p>
          <div class="vocab-foot">
            <span
              class="count-tip"
              :title="'复习 ' + row.review_count + ' 次 · 认错 ' + row.wrong_count + ' 次'"
            >
              复 {{ row.review_count }} · 错 {{ row.wrong_count }}
            </span>
            <span class="vocab-ops">
              <button class="op-link" @click.stop="editFromDetail(row)">编辑</button>
              <button class="op-link danger" @click.stop="remove(row)">删除</button>
            </span>
          </div>
        </article>
      </div>
      <div class="pagination-wrap">
        <UiPagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          :sizes="[15, 30, 60]"
          @change="loadList"
        />
      </div>
    </template>

    <!-- 生词详情（整卡可点打开） -->
    <UiModal v-model="detailVisible" :title="detailRow ? '生词详情' : ''" size="md">
      <div v-if="detailRow" class="vd">
        <div class="vd-head">
          <span class="vd-word serif">{{ detailRow.word }}</span>
          <span v-if="detailRow.kind === 'phrase'" class="vocab-kind">词语</span>
          <span
            class="m-dots"
            :title="masteryLabel(detailRow.mastery_level)"
            :class="{ mastered: detailRow.mastery_level >= 5 }"
          >
            <i v-for="d in 5" :key="d" :class="{ on: d <= detailRow.mastery_level }"></i>
          </span>
        </div>
        <p v-if="detailRow.phonetic" class="vd-phonetic">{{ detailRow.phonetic }}</p>
        <div class="vd-sec">
          <div class="block-label">释义</div>
          <p class="vd-meaning">{{ detailRow.meaning || '—' }}</p>
        </div>
        <div v-if="detailRow.example" class="vd-sec">
          <div class="block-label">例句</div>
          <p class="vd-example">{{ detailRow.example }}</p>
        </div>
        <div v-if="detailRow.note" class="vd-sec">
          <div class="block-label">笔记</div>
          <p class="vd-note">{{ detailRow.note }}</p>
        </div>
        <div class="vd-meta">
          <span class="count-tip">{{ masteryLabel(detailRow.mastery_level) }}</span>
          <span class="count-tip"
            >复习 {{ detailRow.review_count }} · 认错 {{ detailRow.wrong_count }}</span
          >
          <span v-if="detailRow.source" class="count-tip">来源 {{ detailRow.source }}</span>
          <span v-if="detailRow.created_at" class="count-tip">{{
            formatTime(detailRow.created_at).slice(0, 10)
          }}</span>
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="detailVisible = false">关闭</UiButton>
        <UiButton variant="outline" @click="editFromDetail(detailRow)">编辑</UiButton>
        <UiButton variant="danger" @click="removeFromDetail(detailRow)">删除</UiButton>
      </template>
    </UiModal>

    <!-- 新增/编辑 -->
    <UiModal v-model="editVisible" :title="editingId ? '编辑生词' : '添加生词'" size="md">
      <div class="edit-form">
        <div class="field-grid">
          <div class="field">
            <label class="field-label required">单词</label>
            <input v-model="form.word" class="field-input" placeholder="如：abandon" />
          </div>
          <div class="field">
            <label class="field-label">音标</label>
            <input v-model="form.phonetic" class="field-input" placeholder="/əˈbændən/" />
          </div>
        </div>
        <div class="field">
          <label class="field-label">释义</label>
          <textarea
            v-model="form.meaning"
            class="field-input"
            rows="2"
            placeholder="v. 放弃；n. 放纵"
          ></textarea>
        </div>
        <div class="field">
          <label class="field-label">例句</label>
          <textarea
            v-model="form.example"
            class="field-input"
            rows="2"
            placeholder="摘自真题的例句更好"
          ></textarea>
        </div>
        <div class="field">
          <label class="field-label">笔记</label>
          <input v-model="form.note" class="field-input" placeholder="词根词缀、易混词、真题考法" />
        </div>
        <div class="field">
          <label class="field-label">来源</label>
          <input
            v-model="form.source"
            class="field-input"
            placeholder="如：2020 Text 2 / 恋练有词 Unit 3"
          />
        </div>
      </div>
      <template #footer>
        <UiButton variant="ghost" @click="editVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="saving" @click="save">
          {{ editingId ? '保存' : '添加' }}
        </UiButton>
      </template>
    </UiModal>

    <!-- 批量导入 -->
    <UiModal v-model="importVisible" title="批量导入生词" size="lg">
      <p class="count-tip" style="margin: 0 0 8px">
        每行一条，支持「单词 释义」「单词,释义」「单词——释义」等格式；已有单词会自动跳过
      </p>
      <textarea
        v-model="importText"
        class="field-input"
        rows="12"
        placeholder="abandon v. 放弃&#10;tidy adj. 整洁的&#10;mitigate v. 缓解，减轻"
      ></textarea>
      <input
        v-model="importSource"
        class="field-input"
        style="margin-top: 10px"
        placeholder="来源（可选）：如 恋练有词 Unit 3"
      />
      <p class="count-tip" style="margin: 8px 0 0">共 {{ importPreview }} 行</p>
      <template #footer>
        <UiButton variant="ghost" @click="importVisible = false">取消</UiButton>
        <UiButton
          variant="primary"
          :loading="importing"
          :disabled="!importPreview"
          @click="doImport"
        >
          导入 {{ importPreview || '' }} 条
        </UiButton>
      </template>
    </UiModal>
  </div>
</template>

<style scoped>
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
@media (max-width: 860px) {
  .stats-strip {
    grid-template-columns: repeat(2, 1fr);
  }
}
.strip-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}
.strip-icon {
  color: var(--accent);
  display: inline-flex;
}
.strip-num {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
}
.strip-label {
  font-size: 11.5px;
  color: var(--ink-3);
}

.dist {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.dist-bars {
  display: flex;
  gap: 5px;
  align-items: flex-end;
  height: 46px;
}
.dist-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.dist-bar {
  width: 14px;
  border-radius: 3px 3px 0 0;
  background: var(--accent);
  opacity: 0.85;
}
.dist-level {
  font-size: 9px;
  color: var(--ink-3);
}

/* 闪卡 */
.flash-zone {
  max-width: 720px;
  margin: 0 auto 20px;
}
.flash-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.flash-head .count-tip {
  flex: 1;
}
.flash-head .ui-button {
  margin-left: 0;
}
/* 翻面视觉移交给了 ui/FlipCard.vue（与公式背诵共用）；这里只管拖拽区、
   判分提示章与换卡入场。 */
.flash-dragzone {
  position: relative;
  --flip-h: 280px;
}
.flash-swap {
  will-change: transform;
}
/* 换卡入场：新词从墨晕里聚现（key 变更自动重放） */
@media (prefers-reduced-motion: no-preference) {
  .flash-swap {
    animation: flash-card-in var(--dur-3) var(--ease-enter) both;
  }
}
@keyframes flash-card-in {
  from {
    opacity: 0;
    filter: blur(5px);
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    filter: blur(0);
    transform: translateY(0);
  }
}
/* 拖拽判分提示章：右=认识（朱砂）/ 左=不认识（淡墨）/ 下=模糊（洒金） */
.swipe-hint {
  position: absolute;
  top: 14px;
  left: 50%;
  translate: -50% 0;
  z-index: 2;
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.1em;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s linear;
}
.swipe-hint.is-known {
  color: #fff;
  background: var(--accent);
}
.swipe-hint.is-unknown {
  color: var(--ink-2);
  background: var(--surface-2);
  border: 1px dashed var(--ink-3);
}
.swipe-hint.is-fuzzy {
  color: var(--gold);
  border: 1.5px solid var(--gold);
}
/* 背面释义逐行显影：翻面后 meaning/example/note 依次推出 */
@media (prefers-reduced-motion: no-preference) {
  .flash-dragzone :deep(.flip-back) > * {
    animation: back-line-in 0.4s var(--ease-enter) both;
  }
  .flash-dragzone :deep(.flip-back) > *:nth-child(2) {
    animation-delay: 0.08s;
  }
  .flash-dragzone :deep(.flip-back) > *:nth-child(3) {
    animation-delay: 0.16s;
  }
}
@keyframes back-line-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.flash-word {
  font-size: 42px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.flash-phonetic {
  color: var(--ink-3);
  font-size: 15px;
}
.flash-meaning {
  font-size: 19px;
  text-align: center;
  font-weight: 600;
  margin: 0;
}
.flash-example {
  font-size: 13px;
  color: var(--ink-2);
  text-align: center;
  font-style: italic;
  margin: 0;
}
.flash-note {
  font-size: 12.5px;
  color: var(--gold);
  text-align: center;
  margin: 0;
}
.flash-word-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.flash-speak {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  color: var(--accent);
  cursor: pointer;
  transition:
    transform var(--dur-1) var(--ease-move),
    background var(--dur-1) var(--ease-enter);
}
.flash-speak:hover {
  background: var(--accent-soft);
  transform: scale(1.08);
}
.flash-speak:active {
  transform: scale(0.94);
}
.flash-ctx {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 92%;
}
.flash-ctx-label {
  font-size: 11.5px;
  color: var(--teal);
  letter-spacing: 0.08em;
  font-weight: 700;
}
.flash-ctx-label.dim {
  color: var(--ink-3);
  font-weight: 400;
}
.flash-ctx-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 10px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-sm);
  background: var(--surface-2);
  cursor: pointer;
  text-align: left;
  transition: background var(--dur-1) var(--ease-enter);
}
.flash-ctx-item:hover {
  background: var(--accent-soft);
}
.flash-ctx-src {
  font-size: 11px;
  color: var(--ink-3);
}
.flash-ctx-snippet {
  font-size: 12.5px;
  color: var(--ink-2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.flash-tip {
  position: absolute;
  bottom: 14px;
  font-size: 11.5px;
  color: var(--ink-3);
  letter-spacing: 0.06em;
}

.grade-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 14px;
}
.grade-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 46px;
  border-radius: 12px;
  border: 1.5px solid var(--line-strong);
  background: var(--surface);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.14s;
}
.grade-row.disabled {
  opacity: 0.45;
  pointer-events: none;
}
.grade-btn kbd {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 5px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-3);
}
.grade-btn.unknown:hover {
  border-color: var(--red);
  color: var(--red);
  background: var(--red-soft);
}
.grade-btn.fuzzy:hover {
  border-color: var(--gold);
  color: var(--gold);
  background: var(--gold-soft);
}
.grade-btn.known:hover {
  border-color: var(--green);
  color: var(--green);
  background: var(--green-soft);
}

.flash-done {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 26px 0;
  text-align: center;
}
.flash-done .year-ring {
  margin-bottom: 2px;
}
.flash-done h3 {
  font-family: var(--font-display);
  font-size: 21px;
}
.done-sub .ok {
  color: var(--green);
}
.done-sub .warn {
  color: var(--gold);
}
.done-sub .bad {
  color: var(--red);
}
.done-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}

/* 词表 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding: 14px 18px;
  position: relative;
  /* backdrop-filter 会创建层叠上下文：不给 z-index 的话，下拉菜单会被后渲染的词卡盖住 */
  z-index: 5;
  border: 1px solid transparent;
  border-radius: var(--r-lg);
  background:
    linear-gradient(var(--surface-glass), var(--surface-glass)) padding-box,
    linear-gradient(
        135deg,
        color-mix(in srgb, var(--accent) 16%, transparent),
        transparent 45%,
        color-mix(in srgb, var(--teal) 14%, transparent)
      )
      border-box;
  box-shadow: var(--shadow-1);
  backdrop-filter: blur(10px) saturate(1.15);
}
.kind-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: var(--surface-2);
  border-radius: 999px;
}
.kind-tab {
  border: none;
  background: transparent;
  color: var(--ink-3);
  font-size: 12.5px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s var(--ease);
}
.kind-tab:hover {
  color: var(--ink);
}
.kind-tab.active {
  background: var(--accent-grad);
  color: #fff;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--accent-hover) 40%, transparent);
}
.filter-search {
  position: relative;
  display: flex;
  align-items: center;
}
.search-icon {
  position: absolute;
  left: 11px;
  color: var(--ink-3);
  pointer-events: none;
}
.filter-search .field-input {
  width: 220px;
  padding-left: 33px;
}

.vocab-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}
.vocab-card {
  cursor: pointer;
  position: relative;
  overflow: hidden;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  transition:
    border-color 0.2s var(--ease),
    box-shadow 0.3s var(--ease),
    transform 0.25s var(--spring);
  animation: vcard-in var(--dur-4) var(--ease-enter) both;
  animation-delay: var(--enter-delay, 0ms);
}
@keyframes vcard-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.vocab-card:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
  box-shadow: var(--shadow-2);
  transform: translateY(-3px);
}
/* 首字母水墨水印 */
.v-mark {
  position: absolute;
  right: 8px;
  bottom: -12px;
  font-size: 58px;
  font-weight: 900;
  line-height: 1;
  color: var(--accent);
  opacity: 0.06;
  transform: rotate(-6deg);
  pointer-events: none;
  user-select: none;
}
.vocab-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.vocab-word {
  font-size: 18px;
  font-weight: 700;
}
.vocab-kind {
  font-size: 11px;
  font-weight: 700;
  color: var(--teal);
  background: var(--teal-soft);
  padding: 2px 7px;
  border-radius: 6px;
}
/* 掌握度墨点 */
.m-dots {
  display: inline-flex;
  gap: 3.5px;
  flex: none;
}
.m-dots i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--line-strong);
  transition:
    background 0.2s var(--ease),
    transform 0.2s var(--spring);
}
.m-dots i.on {
  background: var(--gold);
}
.m-dots.mastered i.on {
  background: var(--green);
}
.vocab-card:hover .m-dots i.on {
  transform: scale(1.25);
}
/* 详情弹窗（整卡可点打开） */
.vd-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.vd-word {
  font-size: 30px;
  font-weight: 900;
  color: var(--ink);
  line-height: 1.2;
}
.vd-phonetic {
  color: var(--ink-3);
  font-size: 13.5px;
  margin-top: 4px;
}
.vd-sec {
  margin-top: 14px;
}
.vd-meaning {
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink);
}
.vd-example {
  font-size: 13.5px;
  font-style: italic;
  color: var(--ink-2);
  line-height: 1.7;
}
.vd-note {
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.7;
  white-space: pre-wrap;
}
.vd-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 16px;
  padding-top: 10px;
  border-top: 1px dashed var(--line-strong);
}
.vocab-meaning {
  font-size: 13px;
  color: var(--ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.vocab-example {
  font-size: 12px;
  color: var(--ink-3);
  font-style: italic;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.vocab-foot {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.vocab-ops {
  display: flex;
  gap: 2px;
}
.op-link {
  border: none;
  background: transparent;
  color: var(--accent-ink);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 6px;
}
.op-link:hover {
  background: var(--accent-soft);
}
.op-link.danger {
  color: var(--red);
}
.op-link.danger:hover {
  background: var(--red-soft);
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 18px;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 13px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.field-label {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--ink-2);
}
.required::after {
  content: ' *';
  color: var(--accent);
}
</style>
