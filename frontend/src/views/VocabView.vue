<script setup>
/**
 * 生词本（英语二核心）：词表管理 + 闪卡快刷 + 批量导入。
 * 复习节奏：认识→阶梯拉远（1/2/4/7/15/30/60 天），模糊→明天，不认识→留在队列。
 */
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import request from '../api/request'
import { useCountUp } from '../utils/useCountUp'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import UiButton from '../ui/UiButton.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiModal from '../ui/UiModal.vue'
import UiPagination from '../ui/UiPagination.vue'
import Icon from '../ui/Icon.vue'

const mode = ref('list') // list | flashcard
const stats = ref({ total: 0, due: 0, mastered: 0, distribution: [] })
const nTotal = useCountUp(computed(() => stats.value.total))
const nDue = useCountUp(computed(() => stats.value.due))
const nMastered = useCountUp(computed(() => stats.value.mastered))

// —— 词表 ——
const loading = ref(false)
const items = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filters = reactive({ search: '', mastery: null, sort: 'created_desc' })

async function loadList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value, sort: filters.sort }
    if (filters.search.trim()) params.search = filters.search.trim()
    if (filters.mastery !== null) params.mastery = filters.mastery
    const res = await request.get('/vocab', { params })
    const data = res.data.data
    items.value = data?.items || []
    total.value = data?.total || 0
  } catch (err) {
  } finally {
    loading.value = false
  }
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

const importPreview = computed(() =>
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
  const lines = importText.value.split('\n').map((line) => line.trim()).filter(Boolean)
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
const cardEl = ref(null)

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
  } else if (flipped.value && event.key === '1') {
    grade('unknown')
  } else if (flipped.value && event.key === '2') {
    grade('fuzzy')
  } else if (flipped.value && event.key === '3') {
    grade('known')
  }
}
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Vocabulary</div>
        <h2>生词本</h2>
        <p class="view-desc">英语二的每日必修：滚动快刷生词，认识→拉远，不认识→今天再见。</p>
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
      </div>
    </div>

    <div class="stats-strip">
      <div class="strip-item card" v-reveal>
        <span class="strip-icon"><Icon name="book" :size="17" /></span>
        <div><div class="strip-num">{{ nTotal }}</div><div class="strip-label">生词总数</div></div>
      </div>
      <div class="strip-item card" v-reveal="50">
        <span class="strip-icon" style="color: var(--gold)"><Icon name="clock" :size="17" /></span>
        <div><div class="strip-num">{{ nDue }}</div><div class="strip-label">今日到期</div></div>
      </div>
      <div class="strip-item card" v-reveal="100">
        <span class="strip-icon" style="color: var(--green)"><Icon name="check" :size="17" /></span>
        <div><div class="strip-num">{{ nMastered }}</div><div class="strip-label">已掌握</div></div>
      </div>
      <div class="strip-item card dist" v-reveal="150">
        <div class="dist-bars">
          <div
            v-for="d in stats.distribution"
            :key="d.mastery"
            class="dist-col"
            :title="`${masteryLabel(d.mastery)}：${d.count} 词`"
          >
            <div class="dist-bar" :style="{ height: Math.max(6, (d.count / Math.max(1, Math.max(...stats.distribution.map((x) => x.count)))) * 40) + 'px' }"></div>
            <span class="dist-level">{{ d.mastery === 0 ? '新' : d.mastery >= 5 ? '✓' : d.mastery }}</span>
          </div>
        </div>
        <span class="count-tip">掌握度分布</span>
      </div>
    </div>

    <!-- 闪卡模式 -->
    <div v-if="mode === 'flashcard'" class="flash-zone card card-pad">
      <template v-if="sessionDone">
        <div class="flash-done">
          <span class="done-icon"><Icon name="check" :size="26" /></span>
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
        <div
          ref="cardEl"
          class="flash-card"
          :class="{ flipped }"
          @click="flipped = !flipped"
        >
          <div class="flash-word serif">{{ currentCard.word }}</div>
          <div v-if="currentCard.phonetic" class="flash-phonetic">{{ currentCard.phonetic }}</div>
          <div v-if="flipped" class="flash-back">
            <p class="flash-meaning">{{ currentCard.meaning || '（未填写释义）' }}</p>
            <p v-if="currentCard.example" class="flash-example">{{ currentCard.example }}</p>
            <p v-if="currentCard.note" class="flash-note">{{ currentCard.note }}</p>
          </div>
          <span v-else class="flash-tip">点击卡片或按空格查看释义</span>
        </div>
        <div class="grade-row" :class="{ disabled: !flipped }">
          <button type="button" class="grade-btn unknown" :disabled="!flipped" @click="grade('unknown')">
            <Icon name="x" :size="17" />
            不认识
            <kbd>1</kbd>
          </button>
          <button type="button" class="grade-btn fuzzy" :disabled="!flipped" @click="grade('fuzzy')">
            <Icon name="refresh" :size="17" />
            模糊
            <kbd>2</kbd>
          </button>
          <button type="button" class="grade-btn known" :disabled="!flipped" @click="grade('known')">
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
          :options="['生词', 'L1', 'L2', 'L3', 'L4', '已掌握'].map((label, i) => ({ label, value: i }))"
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

      <UiEmpty v-if="!items.length && !loading" text="生词本还是空的，粘贴词表批量导入或逐个添加" icon="book" />
      <div v-else class="vocab-grid">
        <article v-for="row in items" :key="row.id" class="vocab-card card">
          <div class="vocab-head">
            <span class="vocab-word serif">{{ row.word }}</span>
            <UiTag size="sm" :color="row.mastery_level >= 5 ? 'var(--green)' : row.mastery_level >= 1 ? 'var(--gold)' : ''">
              {{ masteryLabel(row.mastery_level) }}
            </UiTag>
          </div>
          <p class="vocab-meaning">{{ row.meaning || '—' }}</p>
          <p v-if="row.example" class="vocab-example">{{ row.example }}</p>
          <div class="vocab-foot">
            <span class="count-tip" :title="'复习 ' + row.review_count + ' 次 · 认错 ' + row.wrong_count + ' 次'">
              复 {{ row.review_count }} · 错 {{ row.wrong_count }}
            </span>
            <span class="vocab-ops">
              <button class="op-link" @click="openEdit(row)">编辑</button>
              <button class="op-link danger" @click="remove(row)">删除</button>
            </span>
          </div>
        </article>
      </div>
      <div class="pagination-wrap">
        <UiPagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="total"
          :sizes="[20, 50, 100]"
          @change="loadList"
        />
      </div>
    </template>

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
          <textarea v-model="form.meaning" class="field-input" rows="2" placeholder="v. 放弃；n. 放纵"></textarea>
        </div>
        <div class="field">
          <label class="field-label">例句</label>
          <textarea v-model="form.example" class="field-input" rows="2" placeholder="摘自真题的例句更好"></textarea>
        </div>
        <div class="field">
          <label class="field-label">笔记</label>
          <input v-model="form.note" class="field-input" placeholder="词根词缀、易混词、真题考法" />
        </div>
        <div class="field">
          <label class="field-label">来源</label>
          <input v-model="form.source" class="field-input" placeholder="如：2020 Text 2 / 恋练有词 Unit 3" />
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
      <input v-model="importSource" class="field-input" style="margin-top: 10px" placeholder="来源（可选）：如 恋练有词 Unit 3" />
      <p class="count-tip" style="margin: 8px 0 0">共 {{ importPreview }} 行</p>
      <template #footer>
        <UiButton variant="ghost" @click="importVisible = false">取消</UiButton>
        <UiButton variant="primary" :loading="importing" :disabled="!importPreview" @click="doImport">
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
@media (max-width: 860px) { .stats-strip { grid-template-columns: repeat(2, 1fr); } }
.strip-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}
.strip-icon { color: var(--accent); display: inline-flex; }
.strip-num {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
}
.strip-label { font-size: 11.5px; color: var(--ink-3); }

.dist { flex-direction: column; align-items: flex-start; gap: 6px; }
.dist-bars { display: flex; gap: 5px; align-items: flex-end; height: 46px; }
.dist-col { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.dist-bar { width: 14px; border-radius: 3px 3px 0 0; background: var(--accent); opacity: 0.85; }
.dist-level { font-size: 9px; color: var(--ink-3); }

/* 闪卡 */
.flash-zone { max-width: 720px; margin: 0 auto 20px; }
.flash-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.flash-head .count-tip { flex: 1; }
.flash-head .ui-button { margin-left: 0; }
.flash-card {
  position: relative;
  min-height: 260px;
  border: 1.5px solid var(--line-strong);
  border-radius: var(--r-xl);
  background: linear-gradient(180deg, var(--surface), var(--surface-2));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 34px 28px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.12s;
  user-select: none;
}
.flash-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-2);
}
.flash-card:active { transform: scale(0.995); }
.flash-card.flipped { border-color: var(--teal); }
.flash-word { font-size: 42px; font-weight: 700; letter-spacing: 0.02em; }
.flash-phonetic { color: var(--ink-3); font-size: 15px; }
.flash-back {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: reveal-in 0.3s ease both;
}
@keyframes reveal-in {
  from { opacity: 0; transform: translateY(6px); }
}
.flash-meaning { font-size: 19px; text-align: center; font-weight: 600; }
.flash-example { font-size: 13px; color: var(--ink-2); text-align: center; font-style: italic; }
.flash-note { font-size: 12.5px; color: var(--gold); text-align: center; }
.flash-tip { position: absolute; bottom: 14px; font-size: 11.5px; color: var(--ink-3); letter-spacing: 0.06em; }

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
.grade-row.disabled { opacity: 0.45; pointer-events: none; }
.grade-btn kbd {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 5px;
  border: 1px solid var(--line);
  background: var(--surface-2);
  color: var(--ink-3);
}
.grade-btn.unknown:hover { border-color: var(--red); color: var(--red); background: var(--red-soft); }
.grade-btn.fuzzy:hover { border-color: var(--gold); color: var(--gold); background: var(--gold-soft); }
.grade-btn.known:hover { border-color: var(--green); color: var(--green); background: var(--green-soft); }

.flash-done {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 26px 0;
  text-align: center;
}
.done-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: var(--green-soft);
  color: var(--green);
}
.flash-done h3 { font-family: var(--font-display); font-size: 21px; }
.done-sub .ok { color: var(--green); }
.done-sub .warn { color: var(--gold); }
.done-sub .bad { color: var(--red); }
.done-actions { display: flex; gap: 10px; margin-top: 6px; }

/* 词表 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.filter-search { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 11px; color: var(--ink-3); pointer-events: none; }
.filter-search .field-input { width: 220px; padding-left: 33px; }

.vocab-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}
.vocab-card {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.vocab-card:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--line));
  box-shadow: var(--shadow-1);
  transform: translateY(-2px);
}
.vocab-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.vocab-word { font-size: 18px; font-weight: 700; }
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
.vocab-ops { display: flex; gap: 2px; }
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
.op-link:hover { background: var(--accent-soft); }
.op-link.danger { color: var(--red); }
.op-link.danger:hover { background: var(--red-soft); }

.pagination-wrap { display: flex; justify-content: center; margin-top: 18px; }

.edit-form { display: flex; flex-direction: column; gap: 13px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field-label { font-size: 12.5px; font-weight: 700; color: var(--ink-2); }
.required::after { content: ' *'; color: var(--accent); }
</style>
