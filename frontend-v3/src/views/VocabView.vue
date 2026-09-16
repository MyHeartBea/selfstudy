<!--
  VocabView —— 生词本（星图词典）
  ---------------------------------------------------------------------------
  用户要求："生词部分同样借鉴 v2 版本，要有明确的翻动效果，有明确的正确和错误动态反应"。
  所以这一页的核心不是数据表，而是**翻卡**：

    · 真 3D 翻转：舞台 perspective + 卡片 preserve-3d + rotateY(180deg)
      （手法取自 v2，视觉落到本设计系统：正面只给词与音标，背面是释义与例句）
    · **三档反馈各有明确动效**：
        认识   - 青光自边缘向外扩散
        模糊   - 琥珀描边一次呼吸
        不认识 - 红移脉冲 + 轻微抖动（被"撞"一下的物理感）
      反馈先播约 620ms 再进入下一张 —— 让"判对/判错"这件事被看见；期间禁止重复提交
    · 键位与 v2 一致：空格翻面 · **1 不认识 · 2 模糊 · 3 认识**
      （此前我做成了 1=认识，与 v2 相反，已纠正）

  契约：/api/vocab 分页对象；/api/vocab/due **裸数组**；
        POST /api/vocab/{id}/review body { result: 'known' | 'fuzzy' | 'unknown' }（字符串，非布尔）
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { vocabApi } from '../core/api'
import { usePageMotion } from '../design/usePageMotion'
import { toast } from '../ui/toast'
import InkDot from '../ui/InkDot.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiField from '../ui/UiField.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const loading = ref(true)
const errorText = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const PAGE_SIZE = 24

const stats = ref(null)

/* ── 闪卡队列 ─────────────────────────────────────────────── */
const queue = ref([])
const qi = ref(0)
const flipped = ref(false)
const busy = ref(false)
/** 当前这一张的反馈状态：'' | 'known' | 'fuzzy' | 'unknown' */
const feedback = ref('')
const tally = ref({ known: 0, fuzzy: 0, unknown: 0 })

const current = computed(() => queue.value[qi.value] || null)
const queueDone = computed(() => queue.value.length > 0 && qi.value >= queue.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const masteryOf = (w) => Math.max(1, Math.min(5, Math.round((w.mastery_level ?? 0) / 20) || 1))

/** 键位映射与 v2 对齐：1 不认识 / 2 模糊 / 3 认识 */
const GRADE_BY_KEY = { 1: 'unknown', 2: 'fuzzy', 3: 'known' }

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
    feedback.value = ''
    tally.value = { known: 0, fuzzy: 0, unknown: 0 }
    if (!queue.value.length) toast.info('今天没有到期的生词')
  } catch (e) {
    toast.error(e?.message || '无法开始闪卡')
  }
}

async function grade(result) {
  if (!current.value || busy.value || feedback.value) return
  busy.value = true
  feedback.value = result
  try {
    await vocabApi.review(current.value.id, result)
    tally.value[result] += 1
  } catch (e) {
    toast.error(e?.message || '提交失败')
    feedback.value = ''
    busy.value = false
    return
  }
  // 反馈动效播完再进下一张（620ms 与 CSS 动画时长一致）
  setTimeout(() => {
    qi.value += 1
    flipped.value = false
    feedback.value = ''
    busy.value = false
    if (qi.value >= queue.value.length) {
      Promise.all([load(), loadStats()])
      toast.success('本轮闪卡完成')
    }
  }, 620)
}

function onKey(e) {
  if (!queue.value.length || queueDone.value) return
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea') return
  if (e.key === ' ') {
    e.preventDefault()
    if (!feedback.value) flipped.value = !flipped.value
    return
  }
  const g = GRADE_BY_KEY[e.key]
  if (g && flipped.value) grade(g)
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
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <h1 class="mono page-h1">生词本</h1>
      <span class="mono">
        {{ stats?.total ?? total }} 词 · 已掌握 {{ stats?.mastered ?? 0 }} · 待复习
        {{ stats?.due ?? 0 }}
      </span>
    </header>

    <!-- ── 闪卡区 ──────────────────────────────────────────── -->
    <section v-if="queue.length && !queueDone" class="flash reveal" data-reveal>
      <div class="fmeta mono">
        <span class="num">{{ qi + 1 }} / {{ queue.length }}</span>
        <span class="tally">
          认识 <b class="ok">{{ tally.known }}</b> · 模糊 <b class="warn">{{ tally.fuzzy }}</b> ·
          不认识 <b class="bad">{{ tally.unknown }}</b>
        </span>
        <span class="keys">空格翻面 · 1 不认识 · 2 模糊 · 3 认识</span>
      </div>

      <!-- 3D 翻转：舞台给透视，卡片保留 3D -->
      <div class="stage">
        <div
          class="card"
          :class="{ flipped, [`fb-${feedback}`]: !!feedback }"
          role="button"
          tabindex="0"
          :aria-label="flipped ? '已翻面，显示释义' : '点按查看释义'"
          @click="!feedback && (flipped = !flipped)"
          @keydown.enter.prevent="!feedback && (flipped = !flipped)"
        >
          <!-- 正面：只给词与音标 -->
          <div class="face front">
            <span class="idx mono" aria-hidden="true">{{ String(qi + 1).padStart(3, '0') }}</span>
            <h2 class="word">{{ current?.word }}</h2>
            <span v-if="current?.phonetic" class="phon mono">{{ current.phonetic }}</span>
            <span class="mono hint">点按或按空格查看释义</span>
          </div>

          <!-- 背面：释义、例句、掌握度墨线 -->
          <div class="face back">
            <span class="bar" :style="{ width: masteryOf(current || {}) * 20 + '%' }"></span>
            <p class="meaning">{{ current?.meaning || '（无释义）' }}</p>
            <p v-if="current?.example" class="example" lang="en">{{ current.example }}</p>
            <span v-if="current?.note" class="note">{{ current.note }}</span>
            <span class="mono hint">判断后自动进入下一张</span>
          </div>

          <!-- 反馈环：三档共用同一元素、只换色，避免三套 DOM -->
          <span class="ring" aria-hidden="true"></span>
        </div>
      </div>

      <div class="grades">
        <UiButton variant="quiet" :disabled="!flipped || !!feedback" @click="grade('unknown')">
          不认识（1）
        </UiButton>
        <UiButton :disabled="!flipped || !!feedback" @click="grade('fuzzy')">模糊（2）</UiButton>
        <UiButton variant="solid" :disabled="!flipped || !!feedback" @click="grade('known')">
          认识（3）
        </UiButton>
      </div>
    </section>

    <UiEmpty
      v-else-if="queueDone"
      title="本轮闪卡完成"
      :hint="`认识 ${tally.known} · 模糊 ${tally.fuzzy} · 不认识 ${tally.unknown}`"
    >
      <template #action>
        <UiButton variant="solid" @click="startFlashcards">再来一轮</UiButton>
      </template>
    </UiEmpty>

    <!-- ── 词表：两列密排（词典密度，不是一行一条的表格）────── -->
    <section class="listwrap reveal" data-reveal>
      <div class="tools">
        <UiField v-model="search" label="搜索" placeholder="单词或释义" />
        <UiButton variant="solid" @click="startFlashcards">
          开始闪卡（{{ stats?.due ?? 0 }} 待复习）
        </UiButton>
      </div>

      <UiEmpty v-if="loading" variant="skeleton" :rows="3" />
      <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText" />
      <UiEmpty
        v-else-if="!filtered.length"
        title="还没有生词"
        hint="在英语精读里点词入本，或手动添加"
      />

      <div v-else class="lex">
        <article v-for="w in filtered" :key="w.id" class="entry">
          <div class="eline">
            <span class="term">{{ w.word }}</span>
            <span v-if="w.phonetic" class="pho mono">{{ w.phonetic }}</span>
            <span class="mast"><InkDot :value="masteryOf(w)" label="掌握度" /></span>
          </div>
          <p class="mean">{{ w.meaning }}</p>
          <p v-if="w.example" class="ex" lang="en">{{ w.example }}</p>
          <div class="emeta mono">
            <span v-if="w.review_count">复习 {{ w.review_count }} 次</span>
            <span v-if="w.note" class="pos">{{ w.note }}</span>
          </div>
        </article>
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
  margin-bottom: clamp(16px, 3vh, 30px);
  flex-wrap: wrap;
}

/* ── 闪卡 ───────────────────────────────────────────────── */
.flash {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: clamp(26px, 4.5vh, 48px);
}
.fmeta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  color: var(--ink-3);
  flex-wrap: wrap;
}
.fmeta .num {
  color: var(--ink-0);
}
.tally b {
  font-weight: 500;
}
.tally .ok {
  color: var(--vein);
}
.tally .warn {
  color: var(--gold);
}
.tally .bad {
  color: var(--redshift);
}

/* 舞台给透视，卡片保留 3D，翻转才像真的翻 */
.stage {
  perspective: 1400px;
}
.card {
  position: relative;
  min-height: clamp(200px, 30vh, 280px);
  transform-style: preserve-3d;
  transition:
    transform 0.62s var(--e-settle),
    box-shadow 0.4s var(--e-settle);
  cursor: pointer;
  user-select: none;
}
.card.flipped {
  transform: rotateY(180deg);
}
.card:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}
.face {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: clamp(22px, 4vw, 38px);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--sky-1);
  backface-visibility: hidden;
  overflow: hidden;
}
/* 背面默认朝后，翻转后面对用户 */
.face.back {
  transform: rotateY(180deg);
  background: var(--sky-2);
}
.idx {
  position: absolute;
  left: 14px;
  bottom: 12px;
  color: var(--ink-3);
}
.word {
  font-size: clamp(1.8rem, 5vw, 3.1rem);
  font-weight: 500;
  letter-spacing: -0.03em;
  text-align: center;
  overflow-wrap: anywhere;
}
.phon {
  color: var(--vein);
}
.hint {
  color: var(--ink-3);
  margin-top: 4px;
}
.meaning {
  font-size: clamp(1.1rem, 2.2vw, 1.6rem);
  line-height: 1.6;
  text-align: center;
  color: var(--ink-0);
  max-width: 52ch;
  overflow-wrap: anywhere;
}
.example {
  color: var(--ink-1);
  font-size: var(--fs-sm);
  line-height: 1.8;
  text-align: center;
  max-width: 58ch;
  overflow-wrap: anywhere;
}
.note {
  color: var(--ink-2);
  font-size: var(--fs-sm);
}
/* 背面顶部墨线：长度 = 掌握度（把"记住多少"画出来） */
.bar {
  position: absolute;
  left: 0;
  top: 0;
  height: 2px;
  background: var(--vein);
  transition: width 0.6s var(--e-settle);
}

/* ── 三档反馈：同一元素换色，避免三套 DOM ─────────────── */
.ring {
  position: absolute;
  inset: 0;
  border: 2px solid transparent;
  border-radius: var(--radius);
  pointer-events: none;
  opacity: 0;
}
/* 认识：青光自边缘向外扩散 */
.fb-known .ring {
  border-color: var(--vein);
  animation: fb-known 0.62s var(--e-settle);
}
.fb-known .face.back {
  border-color: var(--vein);
}
@keyframes fb-known {
  0% {
    opacity: 1;
    box-shadow: 0 0 0 0 oklch(0.775 0.098 200 / 0.55);
  }
  100% {
    opacity: 0;
    box-shadow: 0 0 0 22px oklch(0.775 0.098 200 / 0);
  }
}
/* 模糊：琥珀描边一次呼吸 */
.fb-fuzzy .ring {
  border-color: var(--gold);
  animation: fb-fuzzy 0.62s var(--e-settle);
}
.fb-fuzzy .face.back {
  border-color: var(--gold);
}
@keyframes fb-fuzzy {
  0%,
  100% {
    opacity: 0.2;
  }
  50% {
    opacity: 0.95;
  }
}
/* 不认识：红移边框 + 轻微抖动（被"撞"一下的物理感） */
.fb-unknown .ring {
  border-color: var(--redshift);
  animation: fb-unknown 0.62s var(--e-flare);
}
.fb-unknown .face.back {
  border-color: var(--redshift);
}
.fb-unknown {
  animation: fb-shake 0.42s var(--e-flare);
}
@keyframes fb-unknown {
  0% {
    opacity: 1;
    box-shadow: 0 0 0 0 oklch(0.665 0.196 34 / 0.6);
  }
  100% {
    opacity: 0;
    box-shadow: 0 0 0 26px oklch(0.665 0.196 34 / 0);
  }
}
@keyframes fb-shake {
  0%,
  100% {
    translate: 0 0;
  }
  25% {
    translate: -5px 0;
  }
  60% {
    translate: 4px 0;
  }
}

.grades {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
}

/* ── 词表：两列密排 ─────────────────────────────────────── */
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
.lex {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 1px;
  background: var(--line);
  border: 1px solid var(--line);
}
.entry {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px 14px 13px;
  background: var(--sky-1);
  transition: background 0.3s var(--e-settle);
}
.entry:hover {
  background: var(--sky-2);
}
.eline {
  display: flex;
  align-items: baseline;
  gap: 9px;
  flex-wrap: wrap;
}
.term {
  color: var(--ink-0);
  font-weight: 500;
  letter-spacing: 0.01em;
  overflow-wrap: anywhere;
}
.pho {
  color: var(--vein);
}
.mast {
  margin-left: auto;
}
.mean {
  color: var(--ink-1);
  font-size: var(--fs-sm);
  line-height: 1.65;
  overflow-wrap: anywhere;
}
.ex {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 1.7;
  /* 例句两行截断：词表靠"扫" */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.emeta {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3);
  flex-wrap: wrap;
}
.pos {
  padding: 0 5px;
  border: 1px solid var(--line-strong);
  border-radius: 2px;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
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
  .tools {
    grid-template-columns: 1fr;
  }
}
@media (prefers-reduced-motion: reduce) {
  .card {
    transition: none;
  }
  .fb-unknown {
    animation: none;
  }
  .fb-known .ring,
  .fb-fuzzy .ring,
  .fb-unknown .ring {
    animation: none;
  }
}
</style>
