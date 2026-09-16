<!--
  VocabView —— 生词本（闪卡快刷）
  ---------------------------------------------------------------------------
  契约要点（基线实测，易错）：
    /api/vocab        - 分页对象 { items, total, page, page_size }
    /api/vocab/due    - **裸数组**（不是分页对象）
    /api/vocab/stats  - { total, mastered, due, distribution:[{mastery,count}] }
    POST /api/vocab/{id}/review body { result: 'known' | 'fuzzy' | 'unknown' }
      —— 结果是**三档字符串**，不是布尔（与错题复习的 result: bool 不同）

  交互：认识 / 模糊 / 不认识 三档，键盘 1/2/3 + 空格翻面。
  阶梯由后端计算（1/2/4/7/15/30/60 天），前端只报结果，不自己算间隔。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { usePageMotion } from '../design/usePageMotion'

import { vocabApi } from '../core/api'
import { toast } from '../ui/toast'
import InkDot from '../ui/InkDot.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'

const pageRoot = ref(null)
const loading = ref(true)
const errorText = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const PAGE_SIZE = 30

const stats = ref(null)

/* 闪卡队列 */
const queue = ref([])
const qi = ref(0)
const flipped = ref(false)
const busy = ref(false)
const doneStats = ref({ known: 0, fuzzy: 0, unknown: 0 })

const current = computed(() => queue.value[qi.value] || null)
const queueDone = computed(() => qi.value >= queue.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const masteryOf = (w) => Math.max(1, Math.min(5, Math.round((w.mastery_level ?? 0) / 20) || 1))

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const data = await vocabApi.list({ page: page.value, page_size: PAGE_SIZE })
    items.value = data?.items || []
    total.value = data?.total ?? items.value.length
  } catch (e) {
    errorText.value = e?.message || '无法载入生词'
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = await vocabApi.stats()
  } catch {
    stats.value = null
  }
}

async function startFlashcards() {
  try {
    const data = await vocabApi.due(30)
    queue.value = Array.isArray(data) ? data : data?.items || []
    qi.value = 0
    flipped.value = false
    doneStats.value = { known: 0, fuzzy: 0, unknown: 0 }
    if (!queue.value.length) toast.info('今天没有到期的生词')
  } catch (e) {
    toast.error(e?.message || '无法开始闪卡')
  }
}

/** 三档结果：字符串而非布尔 */
async function grade(result) {
  if (!current.value || busy.value) return
  busy.value = true
  try {
    await vocabApi.review(current.value.id, result)
    doneStats.value[result] += 1
    qi.value += 1
    flipped.value = false
    if (qi.value >= queue.value.length) {
      await Promise.all([load(), loadStats()])
      toast.success('本轮闪卡完成')
    }
  } catch (e) {
    toast.error(e?.message || '提交失败')
  } finally {
    busy.value = false
  }
}

function onKey(e) {
  if (!queue.value.length || queueDone.value) return
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  if (e.key === ' ') {
    e.preventDefault()
    flipped.value = !flipped.value
  } else if (flipped.value && e.key === '1') grade('known')
  else if (flipped.value && e.key === '2') grade('fuzzy')
  else if (flipped.value && e.key === '3') grade('unknown')
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(
    (w) => (w.word || '').toLowerCase().includes(q) || (w.meaning || '').toLowerCase().includes(q),
  )
})

onMounted(() => {
  load()
  loadStats()
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

/** 页面级动效：错峰入场 + 视差 + 磁吸 + 路径描绘（见 design/usePageMotion） */
usePageMotion(pageRoot, { stagger: 55 })
</script>

<template>
  <main ref="pageRoot" id="main" class="pad">
    <header class="head">
      <span class="mono">[06] LEXICON · 生词本</span>
      <span class="mono">
        {{ stats?.total ?? total }} 词 · 已掌握 {{ stats?.mastered ?? 0 }} · 待复习
        {{ stats?.due ?? 0 }}
      </span>
    </header>

    <!-- 闪卡区：队列存在时占据主位 -->
    <section v-if="queue.length && !queueDone" class="flash reveal" data-reveal>
      <div class="fmeta">
        <span class="mono">{{ qi + 1 }} / {{ queue.length }}</span>
        <span class="mono">空格翻面 · 1 认识 · 2 模糊 · 3 不认识</span>
      </div>

      <button class="card" type="button" @click="flipped = !flipped">
        <span class="word">{{ current?.word }}</span>
        <span v-if="current?.phonetic" class="mono phon">{{ current.phonetic }}</span>

        <template v-if="flipped">
          <span class="meaning">{{ current?.meaning || '（无释义）' }}</span>
          <span v-if="current?.example" class="ex">{{ current.example }}</span>
        </template>
        <span v-else class="mono hint">点击或按空格查看释义</span>
      </button>

      <div class="grades">
        <UiButton variant="solid" :disabled="!flipped" :loading="busy" @click="grade('known')">
          认识（1）
        </UiButton>
        <UiButton :disabled="!flipped" :loading="busy" @click="grade('fuzzy')">模糊（2）</UiButton>
        <UiButton variant="quiet" :disabled="!flipped" :loading="busy" @click="grade('unknown')">
          不认识（3）
        </UiButton>
      </div>
    </section>

    <UiEmpty
      v-else-if="queue.length && queueDone"
      title="本轮闪卡完成"
      :hint="`认识 ${doneStats.known} · 模糊 ${doneStats.fuzzy} · 不认识 ${doneStats.unknown}`"
    >
      <template #action>
        <UiButton variant="solid" @click="startFlashcards">再来一轮</UiButton>
      </template>
    </UiEmpty>

    <!-- 词表 -->
    <section class="listwrap reveal" data-reveal>
      <div class="tools">
        <UiField v-model="search" label="搜索" placeholder="单词或释义" />
        <UiButton variant="solid" @click="startFlashcards"
          >开始闪卡（{{ stats?.due ?? 0 }} 待复习）</UiButton
        >
      </div>

      <UiEmpty v-if="loading" variant="skeleton" :rows="3" />
      <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText" />
      <UiEmpty
        v-else-if="!filtered.length"
        title="还没有生词"
        hint="在英语精读里点词入本，或手动添加"
      />

      <div v-else class="rows">
        <div v-for="w in filtered" :key="w.id" class="row">
          <span class="w">{{ w.word }}</span>
          <span class="ph mono">{{ w.phonetic || '' }}</span>
          <span class="mn">{{ w.meaning }}</span>
          <span class="mt"><InkDot :value="masteryOf(w)" label="掌握度" /></span>
          <span class="mono rc">{{ w.review_count || 0 }} 次</span>
        </div>
      </div>

      <div v-if="totalPages > 1" class="pager">
        <UiButton :disabled="page <= 1" @click="((page -= 1), load())">上一页</UiButton>
        <span class="mono pnum">{{ page }} / {{ totalPages }}</span>
        <UiButton :disabled="page >= totalPages" @click="((page += 1), load())">下一页</UiButton>
      </div>
    </section>
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
  margin-bottom: clamp(16px, 3vh, 30px);
}

/* 闪卡 */
.flash {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: clamp(24px, 4vh, 44px);
}
.fmeta {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  color: var(--ink-3);
}
.card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: clamp(180px, 30vh, 260px);
  padding: 28px;
  background: var(--sky-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  text-align: center;
  transition:
    border-color 0.25s var(--e-settle),
    background 0.25s var(--e-settle);
}
.card:hover {
  border-color: var(--vein);
  background: var(--sky-2);
}
.word {
  font-size: clamp(1.8rem, 5vw, 3rem);
  font-weight: 500;
  letter-spacing: -0.03em;
}
.phon {
  color: var(--vein);
}
.meaning {
  font-size: var(--fs-h2);
  line-height: 1.6;
  color: var(--ink-0);
  max-width: 54ch;
}
.ex {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  max-width: 60ch;
  line-height: 1.7;
}
.hint {
  color: var(--ink-3);
}
.grades {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* 词表 */
.listwrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.tools {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.row {
  display: grid;
  grid-template-columns: minmax(90px, 140px) minmax(0, 110px) minmax(0, 1fr) 70px 54px;
  gap: 12px;
  align-items: center;
  padding: 11px 14px;
  background: var(--sky-1);
  font-size: var(--fs-sm);
}
.row:hover {
  background: var(--sky-2);
}
.w {
  font-weight: 500;
  color: var(--ink-0);
}
.ph {
  color: var(--vein);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mn {
  color: var(--ink-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rc {
  text-align: right;
  color: var(--ink-3);
}
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.pnum {
  color: var(--ink-2);
}

@media (max-width: 820px) {
  .row {
    grid-template-columns: 1fr auto;
    row-gap: 4px;
  }
  .mn {
    grid-column: 1 / -1;
    white-space: normal;
  }
  .tools {
    grid-template-columns: 1fr;
  }
}
</style>
