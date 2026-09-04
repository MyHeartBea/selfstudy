<script setup>
/** 英语整篇精读面板：原文(分段) → 全文翻译 → 句子拆解 → 猜词&重点短语(全选入生词本) → 题目列表(多题)。
 * 点词查义；多题可「存为另一题」切到表单保存。 */
import { computed, reactive, ref } from 'vue'

import request from '../api/request'
import { toast } from '../ui/toast'
import UiButton from '../ui/UiButton.vue'
import UiModal from '../ui/UiModal.vue'
import Icon from '../ui/Icon.vue'

const props = defineProps({
  parsed: { type: Object, default: null },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['save-question', 'saved'])

// —— 点词查义 ——
const lookupVisible = ref(false)
const lookupLoading = ref(false)
const lookupWord = ref('')
const lookupData = ref(null)

const extractedMap = computed(() => {
  const map = new Map()
  for (const w of props.parsed?.english_words || []) {
    map.set(String(w.word || '').toLowerCase(), w)
  }
  return map
})

// —— 原文分段（按空行/换行分段）—— 
const paragraphs = computed(() => {
  const raw = props.parsed?.passage_text || ''
  return raw
    .split(/\n+/)
    .map((t) => t.trim())
    .filter(Boolean)
})

// —— 原文对照（左右两栏）：直接用 AI 分好的句子 + 其译文，保证句句都有翻译 ——
const bilingual = computed(() => {
  const ss = props.parsed?.english_sentences || []
  const items = ss
    .filter((s) => s.text)
    .map((s) => ({
      english: s.text,
      translation: s.translation || '',
      structure: s.structure || '',
      pattern: s.pattern || '',
    }))
  if (items.length) return items
  // 兜底：按段落切句（无逐句译文时显示原文）
  return paragraphs.value
    .flatMap((pp) => String(pp || '').split(/(?<=[.!?])\s+/).map((t) => t.trim()).filter(Boolean))
    .map((es) => ({ english: es, translation: '', structure: '', pattern: '' }))
})

// —— 句子拆解 ——
const sentences = computed(() => {
  const list = props.parsed?.english_sentences || []
  if (list.length) return list
  return paragraphs.value
    .flatMap((p) => p.split(/(?<=[.!?])\s+/))
    .filter((t) => t.trim())
    .map((t) => ({ text: t.trim(), structure: '', pattern: '', translation: '' }))
})

const CHIP_COLORS = [
  { bg: 'rgba(250, 204, 21, 0.16)', border: 'rgba(250, 204, 21, 0.45)' },
  { bg: 'rgba(192, 132, 252, 0.16)', border: 'rgba(192, 132, 252, 0.45)' },
  { bg: 'rgba(96, 165, 250, 0.16)', border: 'rgba(96, 165, 250, 0.45)' },
  { bg: 'rgba(74, 222, 128, 0.16)', border: 'rgba(74, 222, 128, 0.45)' },
  { bg: 'rgba(251, 146, 60, 0.16)', border: 'rgba(251, 146, 60, 0.45)' },
]
function chipColor(i) { return CHIP_COLORS[i % CHIP_COLORS.length] }

function isExtracted(word) { return extractedMap.value.has(word.toLowerCase()) }

const wordRe = /[A-Za-z]+(?:['-][A-Za-z]+)*/g
function tokenize(text) {
  const out = []
  let last = 0
  const s = String(text || '')
  for (const m of s.matchAll(wordRe)) {
    const idx = m.index
    if (idx > last) out.push({ type: 'text', value: s.slice(last, idx) })
    out.push({ type: 'word', value: m[0] })
    last = idx + m[0].length
  }
  if (last < s.length) out.push({ type: 'text', value: s.slice(last) })
  return out
}

async function openWord(word) {
  lookupWord.value = word
  lookupVisible.value = true
  lookupLoading.value = true
  lookupData.value = null
  const hit = extractedMap.value.get(word.toLowerCase())
  if (hit) {
    lookupData.value = {
      word: hit.word, phonetic: hit.phonetic || '',
      meanings: [{ pos: hit.pos || '', meaning: hit.meaning || '' }],
      example: hit.example || '',
    }
    lookupLoading.value = false
    return
  }
  try {
    const res = await request.get('/ai/sense', { params: { word }, silent: true })
    lookupData.value = res.data.data
  } catch (err) {
    lookupData.value = null
    toast.warning('该词暂未查询到释义，可加入生词本后补充')
  } finally {
    lookupLoading.value = false
  }
}

// —— 批量勾选入生词本 ——
const selected = ref([])
function toggleKey(key) {
  const i = selected.value.indexOf(key)
  if (i === -1) selected.value.push(key)
  else selected.value.splice(i, 1)
}
function toggleAll() {
  if (selected.value.length === vocabOptions.value.length) selected.value = []
  else selected.value = vocabOptions.value.map((o) => o.key)
}

const vocabOptions = computed(() => {
  const opts = []
  for (const w of props.parsed?.english_words || []) {
    opts.push({ key: 'w:' + w.word, word: w.word, meaning: w.meaning || '', phonetic: w.phonetic || '', example: w.example || '', note: w.pos || '', kind: 'word' })
  }
  for (const p of props.parsed?.english_phrases || []) {
    opts.push({ key: 'p:' + p.phrase, word: p.phrase, meaning: p.meaning || '', example: p.example || '', note: p.pos || '', kind: 'phrase' })
  }
  return opts
})
const selectedCount = computed(() => selected.value.length)
const allSelected = computed(() => vocabOptions.value.length > 0 && selected.value.length === vocabOptions.value.length)

const sourceHint = computed(() => {
  const src = props.parsed?.source || props.parsed?.source_name || props.parsed?.source_year || ''
  if (src) return String(src).trim()
  if (props.parsed?.source_type === 'real_exam') return '真题'
  if (props.parsed?.source_type === 'mock') return '模拟题'
  return ''
})

function selectedVocabItems() {
  return vocabOptions.value
    .filter((o) => selected.value.includes(o.key))
    .map((o) => ({ word: o.word, meaning: o.meaning, phonetic: o.phonetic, example: o.example, note: o.note, source: sourceHint.value, kind: o.kind || 'word' }))
}

async function addSelected() {
  if (!selected.value.length) { toast.warning('请先勾选要加入生词本的单词/短语'); return }
  const items = selectedVocabItems()
  try {
    await importVocabItems(items)
    selected.value = []
  } catch (err) {}
}

async function importVocabItems(items) {
  if (!items.length) return
  const res = await request.post('/vocab/import-english', { items, source: sourceHint.value })
  const r = res.data.data
  const existing = items.length - (r.created || 0) - (r.updated || 0)
  toast.success(`已加入生词本：新增 ${r.created} 条${r.updated ? `，补充 ${r.updated}` : ''}${existing > 0 ? `，${existing} 个已存在跳过` : ''}${r.failed?.length ? `，失败 ${r.failed.length}` : ''}`)
  return r
}

// —— 多题列表 ——
const questions = computed(() => {
  const eq = props.parsed?.english_questions || []
  const base = {
    question: props.parsed?.question || '', option_a: props.parsed?.option_a || '', option_b: props.parsed?.option_b || '',
    option_c: props.parsed?.option_c || '', option_d: props.parsed?.option_d || '', correct_answer: props.parsed?.correct_answer || '',
    analysis: props.parsed?.analysis || '', difficulty: props.parsed?.difficulty, difficulty_points: props.parsed?.difficulty_points || '',
    approach: props.parsed?.approach || '', question_type: props.parsed?.question_type || 'choice',
  }
  // 已保存的整篇记录：english_questions 含全部题目（含第 1 题）
  if (eq.length && eq[0] && eq[0].question === base.question) {
    return eq.filter((q) => q && q.question)
  }
  // 分析结果：english_questions 只含第 2 题起，需补上顶层第 1 题
  const list = [base, ...eq]
  return list.filter((q) => q && q.question)
})
const currentQuestion = computed(() => questions.value[0] || null)

function saveAsCurrentQuestion(index) {
  // 把选中的题目移动到顶层，作为表单保存的题目，并从多题池移除
  emit('save-question', index)
}

// —— 对/错标记（默认答错；错的标重点）——
const markState = reactive({}) // key = q.question
function getMark(q) {
  if (markState[q.question]) return markState[q.question]
  if (q.wrong === false) return 'right'
  return 'wrong' // 默认错；保存过的数据用 q.wrong
}
function setMark(q, val) {
  markState[q.question] = val
}
function setAllMark(val) {
  for (const q of questions.value) markState[q.question] = val
}
const savingAll = ref(false)

async function saveAll() {
  if (!questions.value.length) { toast.warning('暂无题目可录入'); return }
  const base = props.parsed || {}
  const qs = questions.value
  const buildQ = (q) => {
    const wrong = getMark(q) === 'wrong'
    return {
      question: q.question,
      option_a: q.option_a || '', option_b: q.option_b || '',
      option_c: q.option_c || '', option_d: q.option_d || '',
      correct_answer: q.correct_answer || '',
      analysis: q.analysis || base.analysis || '',
      difficulty: q.difficulty || base.difficulty || 3,
      difficulty_points: q.difficulty_points || base.difficulty_points || '',
      approach: (wrong ? '❌ 本题答错，需重点复习；' : '') + (q.approach || base.approach || ''),
      wrong: wrong,
    }
  }
  const first = buildQ(qs[0])
  const rest = qs.slice(1).map(buildQ)
  const tags = [...(base.knowledge_tags || []), ...(qs[0].knowledge_tags || [])]
  if (getMark(qs[0]) === 'wrong') tags.push('答题失误')
  const uniq = []
  for (const t of tags) if (t && !uniq.includes(t)) uniq.push(t)
  const payload = {
    subject_id: base.subject_id,
    sub_subject_id: base.sub_subject_id,
    question_type: qs[0].question_type || 'choice',
    question: qs[0].question,
    option_a: first.option_a, option_b: first.option_b,
    option_c: first.option_c, option_d: first.option_d,
    correct_answer: first.correct_answer,
    answer_aliases: [],
    analysis: first.analysis,
    difficulty: first.difficulty,
    difficulty_points: first.difficulty_points,
    knowledge_tags: uniq,
    approach: first.approach,
    source: base.source || '',
    source_type: base.source_type || 'other',
    source_year: base.source_year || '',
    source_name: base.source_name || '',
    images: (base.images || []).slice(),
    passage_text: base.passage_text || '',
    passage_translation: base.passage_translation || '',
    english_sentences: base.english_sentences || [],
    english_phrases: base.english_phrases || [],
    english_words: base.english_words || [],
    english_questions: [first, ...rest],
  }
  savingAll.value = true
  try {
    const res = await request.post('/mistakes', payload, { silent: true })
    const wrongN = qs.filter((q) => getMark(q) === 'wrong').length
    toast.success(`整篇已录入 1 道（含 ${qs.length} 题，答错 ${wrongN}）`)
    // 先跳转，避免生词导入卡住导航；生词后台异步导入
    emit('saved')
    const vocabItems = selectedVocabItems()
    if (vocabItems.length) {
      selected.value = []
      importVocabItems(vocabItems).catch(() => {})
    }
  } catch (err) {
    toast.error(err?.response?.data?.message || '录入失败')
  } finally {
    savingAll.value = false
  }
}
</script>

<template>
  <div class="english-panel">
    <!-- ① 原文对照翻译（左英文 · 右翻译） -->
    <div class="ep-section">
      <div class="ep-section-head"><Icon name="book" :size="15" /><span>原文对照翻译</span><span class="ep-hint">左英语 · 右翻译（点击单词查看释义）</span></div>
      <div v-if="bilingual.length" class="ep-bilingual">
        <div class="ep-bi">
          <template v-for="(item, si) in bilingual" :key="si">
            <p class="ep-bi-en">
              <span v-for="(t, j) in tokenize(item.english)" :key="j">
                <span v-if="t.type === 'text'">{{ t.value }}</span>
                <button v-else type="button" class="ep-word" :class="{ known: isExtracted(t.value) }" @click="openWord(t.value)">{{ t.value }}</button>
              </span>
            </p>
            <p v-if="item.translation" class="ep-bi-cn">{{ item.translation }}</p>
            <p v-else class="ep-bi-cn muted">—</p>
          </template>
        </div>
      </div>
      <p v-else class="muted">（未识别到原文内容）</p>
    </div>

    <!-- ② 题目列表（多题） -->
    <div v-if="questions.length" class="ep-section">
      <div class="ep-section-head">
        <Icon name="target" :size="15" />
        <span>题目与解析（共 {{ questions.length }} 题）</span>
        <span v-if="!readonly" class="ep-hint">标出答错的题，错的会重点标注并录入</span>
      </div>
      <div v-if="!readonly" class="ep-q-actions">
        <UiButton size="sm" variant="primary" :loading="savingAll" @click="saveAll">
          <Icon name="layers" :size="14" />整篇全部录入（{{ questions.length }} 题）
        </UiButton>
        <UiButton size="sm" variant="ghost" @click="setAllMark('wrong')">全部标错</UiButton>
        <UiButton size="sm" variant="ghost" @click="setAllMark('right')">全部标对</UiButton>
      </div>
      <div class="ep-questions">
        <div v-for="(q, qi) in questions" :key="qi" class="ep-question" :class="{ first: qi === 0, wrong: getMark(q) === 'wrong' }">
          <div class="ep-q-head">
            <span class="ep-q-num">第 {{ qi + 1 }} 题</span>
            <span class="ep-q-mark" :class="getMark(q) === 'wrong' ? 'wrong' : 'right'">
              <Icon v-if="getMark(q) === 'wrong'" name="x" :size="12" />
              <Icon v-else name="check" :size="12" />
              {{ getMark(q) === 'wrong' ? '答错·重点' : '答对' }}
            </span>
            <span v-if="!readonly && qi === 0" class="ep-q-current">当前保存题</span>
            <button v-else-if="!readonly" type="button" class="ep-q-save" @click="saveAsCurrentQuestion(qi)">存为另一题</button>
            <span v-if="!readonly" class="ep-q-toggle">
              <button type="button" class="ep-toggle-btn" :class="{ active: getMark(q) === 'wrong' }" @click="setMark(q, 'wrong')">错</button>
              <button type="button" class="ep-toggle-btn ok" :class="{ active: getMark(q) === 'right' }" @click="setMark(q, 'right')">对</button>
            </span>
          </div>
          <p class="ep-question-text">{{ q.question }}</p>
          <div v-if="q.question_type === 'choice'" class="ep-options">
            <div v-for="(ok, k) in ['option_a', 'option_b', 'option_c', 'option_d']" :key="k" class="ep-option">
              <span class="ep-option-letter">{{ 'ABCD'[k] }}</span>
              <span class="ep-option-text">{{ q[ok] }}</span>
              <span v-if="q.correct_answer === 'ABCD'[k]" class="ep-correct">✓</span>
            </div>
          </div>
          <p v-else class="ep-answer">答案：{{ q.correct_answer }}</p>
          <div v-if="q.analysis" class="ep-analysis">{{ q.analysis }}</div>
        </div>
      </div>
    </div>

    <!-- ④ 句子拆解 / 句型分析（每句色块 紧接 该句结构注解，上下结合） -->
    <div v-if="sentences.length" class="ep-section">
      <div class="ep-section-head"><Icon name="list" :size="15" /><span>句子拆解 / 句型分析</span></div>
      <div class="ep-passage">
        <div v-for="(s, i) in sentences" :key="i" class="ep-sent-item">
          <div class="ep-sentence" :style="{ background: chipColor(i).bg, borderColor: chipColor(i).border }">
            <span v-for="(t, j) in tokenize(s.text)" :key="j">
              <span v-if="t.type === 'text'">{{ t.value }}</span>
              <button v-else type="button" class="ep-word" :class="{ known: isExtracted(t.value) }" @click="openWord(t.value)">{{ t.value }}</button>
            </span>
          </div>
          <div v-if="s.pattern || s.structure" class="ep-sent-note">
            <span class="ep-structure-tag">句 {{ i + 1 }}</span>
            <span class="ep-sent-pattern">{{ s.pattern || s.structure }}</span>
            <div v-if="s.structure && s.structure !== s.pattern" class="ep-sent-struct">结构：{{ s.structure }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ⑤ 猜词 & 重点短语（仅智能录入时显示，详情不再展示） -->
    <div v-if="!readonly && vocabOptions.length" class="ep-section">
      <div class="ep-section-head">
        <Icon name="tag" :size="15" /><span>猜词 &amp; 重点短语</span>
        <button type="button" class="ep-select-all" @click="toggleAll">{{ allSelected ? '取消全选' : '一键全选' }}</button>
        <span class="ep-hint">勾选后加入生词本（已存在自动跳过）</span>
      </div>
      <div class="ep-vocab-list">
        <label v-for="o in vocabOptions" :key="o.key" class="ep-vocab-item" :class="{ checked: selected.includes(o.key) }">
          <input type="checkbox" :checked="selected.includes(o.key)" @change="toggleKey(o.key)" />
          <span class="ep-vocab-word">{{ o.word }}</span>
          <span class="ep-vocab-pos">{{ o.note }}</span>
          <span class="ep-vocab-meaning">{{ o.meaning }}</span>
        </label>
      </div>
      <div class="ep-vocab-actions">
        <UiButton size="sm" variant="primary" :disabled="!selectedCount" @click="addSelected">
          <Icon name="plus-circle" :size="14" />加入生词本（{{ selectedCount }}）
        </UiButton>
        <UiButton v-if="selectedCount" size="sm" variant="ghost" @click="selected = []">清空勾选</UiButton>
        <span v-if="selectedCount" class="muted" style="font-size:12px">已勾选 {{ selectedCount }} 项</span>
      </div>
    </div>

    <!-- 点词查义弹窗 -->
    <UiModal v-model="lookupVisible" :title="`词义查询 · ${lookupWord}`" size="sm">
      <div v-if="lookupLoading" class="ep-lookup-loading"><span class="spinner"></span><span>正在查询…</span></div>
      <div v-else-if="lookupData" class="ep-lookup">
        <p class="ep-lookup-phonetic">{{ lookupData.phonetic }}</p>
        <div class="ep-lookup-meanings">
          <div v-for="(m, i) in lookupData.meanings" :key="i" class="ep-lookup-meaning">
            <span v-if="m.pos" class="ep-lookup-pos">{{ m.pos }}</span><span class="ep-lookup-text">{{ m.meaning }}</span>
          </div>
        </div>
        <p v-if="lookupData.example" class="ep-lookup-example">例：{{ lookupData.example }}</p>
      </div>
      <p v-else class="muted">暂未查询到释义。</p>
      <template #footer><UiButton variant="ghost" size="sm" @click="lookupVisible = false">关闭</UiButton></template>
    </UiModal>
  </div>
</template>

<style scoped>
.english-panel { display: flex; flex-direction: column; gap: 18px; }
.ep-section { display: flex; flex-direction: column; gap: 10px; }
.ep-section-head { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; color: var(--ink); }
.ep-section-head .ep-hint { font-size: 12px; color: var(--ink-3); font-weight: 400; }
.ep-section-head svg { color: var(--accent); }

.ep-bilingual { display: flex; flex-direction: column; gap: 14px; }
.ep-bi-block { display: flex; flex-direction: column; gap: 8px; }
.ep-bi { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; align-items: start; }
.ep-bi-en { margin: 0; font-size: 14.5px; line-height: 1.8; color: var(--ink); }
.ep-bi-cn { margin: 0; font-size: 12.5px; line-height: 1.8; color: var(--ink-2); padding-left: 8px; border-left: 2px solid var(--line-strong); }
.ep-word { border: none; background: transparent; color: inherit; font: inherit; padding: 0 1px; cursor: pointer; border-bottom: 1px dashed var(--ink-3); border-radius: 3px; }
.ep-word:hover { background: var(--accent-soft); color: var(--accent-ink); }
.ep-word.known { border-bottom-color: var(--accent); color: var(--accent-ink); }

.ep-translation { margin: 0; font-size: 13.5px; color: var(--ink-2); line-height: 1.8; white-space: pre-wrap; }

.ep-passage { display: flex; flex-direction: column; gap: 10px; }
.ep-sent-item { display: flex; flex-direction: column; gap: 6px; }
.ep-sentence { border: 1px solid; border-radius: 10px; padding: 10px 12px; font-size: 14.5px; line-height: 1.8; color: var(--ink); }
.ep-sent-note { display: flex; flex-direction: column; gap: 5px; padding: 0 4px 0 12px; border-left: 3px solid var(--accent); }
.ep-sent-pattern { font-size: 13px; color: var(--ink); line-height: 1.7; }
.ep-sent-struct { font-size: 12px; color: var(--ink-2); }
.ep-structure-tag { font-size: 11px; font-weight: 700; color: var(--accent-ink); background: var(--accent-soft); padding: 2px 7px; border-radius: 999px; align-self: flex-start; }

.ep-select-all { margin-left: auto; border: 1px solid var(--accent); background: var(--accent-soft); color: var(--accent-ink); font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; cursor: pointer; }
.ep-select-all:hover { background: var(--accent); color: #fff; }

.ep-vocab-list { display: flex; flex-direction: column; gap: 6px; }
.ep-vocab-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 9px; cursor: pointer; transition: all 0.13s; }
.ep-vocab-item:hover { border-color: var(--accent); }
.ep-vocab-item.checked { border-color: var(--green); background: var(--green-soft); }
.ep-vocab-item input { accent-color: var(--accent); }
.ep-vocab-word { font-weight: 600; font-size: 14px; min-width: 130px; }
.ep-vocab-pos { font-size: 11.5px; color: var(--ink-3); background: var(--surface-2); border-radius: 5px; padding: 1px 6px; }
.ep-vocab-meaning { font-size: 12.5px; color: var(--ink-2); }
.ep-vocab-actions { display: flex; align-items: center; gap: 10px; }

.ep-questions { display: flex; flex-direction: column; gap: 12px; }
.ep-q-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.ep-question { padding: 12px 14px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface-2); }
.ep-question.first { border-color: var(--teal); }
.ep-question.wrong { border-color: var(--red); box-shadow: 0 0 0 1px var(--red-soft); }
.ep-q-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
.ep-q-num { font-size: 12px; font-weight: 800; color: var(--accent-ink); background: var(--accent-soft); padding: 2px 8px; border-radius: 6px; }
.ep-q-mark { display: inline-flex; align-items: center; gap: 3px; font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
.ep-q-mark.wrong { color: var(--red); background: var(--red-soft); }
.ep-q-mark.right { color: var(--green); background: var(--green-soft); }
.ep-q-current { font-size: 11.5px; font-weight: 700; color: var(--green); }
.ep-q-save { margin-left: auto; border: 1px solid var(--accent); background: transparent; color: var(--accent-ink); font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 999px; cursor: pointer; }
.ep-q-save:hover { background: var(--accent-soft); }
.ep-q-toggle { display: inline-flex; gap: 3px; }
.ep-toggle-btn { border: 1px solid var(--line-strong); background: var(--surface); color: var(--ink-3); font-size: 11.5px; font-weight: 700; padding: 2px 9px; border-radius: 6px; cursor: pointer; transition: all 0.13s; }
.ep-toggle-btn.active { background: var(--red); border-color: var(--red); color: #fff; }
.ep-toggle-btn.ok.active { background: var(--green); border-color: var(--green); color: #fff; }
.ep-toggle-btn:hover { border-color: var(--accent); }
.ep-question-text { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.ep-options { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.ep-option { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.ep-option-letter { font-weight: 700; color: var(--accent-ink); }
.ep-correct { color: var(--green); font-weight: 700; }
.ep-answer { font-size: 13px; font-weight: 700; margin: 4px 0 8px; }
.ep-analysis { font-size: 13px; color: var(--ink-2); line-height: 1.8; white-space: pre-wrap; }

.ep-lookup-loading { display: flex; align-items: center; gap: 10px; color: var(--ink-2); font-size: 13px; }
.ep-lookup-phonetic { margin: 0 0 8px; font-size: 14px; color: var(--ink-2); }
.ep-lookup-meanings { display: flex; flex-direction: column; gap: 6px; }
.ep-lookup-meaning { display: flex; align-items: baseline; gap: 8px; font-size: 13.5px; }
.ep-lookup-pos { flex: none; font-size: 11.5px; font-weight: 700; color: var(--teal); background: var(--teal-soft); padding: 2px 7px; border-radius: 6px; }
.ep-lookup-example { margin: 10px 0 0; font-size: 12.5px; color: var(--ink-2); font-style: italic; }
.spinner { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--accent-soft); border-top-color: var(--accent); animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
