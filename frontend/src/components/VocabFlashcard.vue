<script setup>
/**
 * 生词闪卡快刷会话（自 VocabView 拆出，自含状态与键盘流）：
 * 挂载即拉到期队列，判分/飞出/语境回链全在本组件内；
 * 会话结束 emit('done') 让父页刷新统计与词表，退出 emit('exit')。
 */
import {
  computed,
  onActivated,
  onDeactivated,
  onMounted,
  onUnmounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRouter } from 'vue-router'

import request from '../api/request'
import { speakEnglish, speechSupported } from '../utils/speech'
import { toast } from '../ui/toast'
import FlipCard from '../ui/FlipCard.vue'
import Icon from '../ui/Icon.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'
import YearRing from '../ui/YearRing.vue'

const emit = defineEmits(['exit', 'done'])
const router = useRouter()

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
const grading = ref(false) // 判分在途锁:双击/连按不会对同一张卡双发请求
// 会话内回队计数:id 映射到 {fuzzy: n, unknown: n}。模糊限 1 次(防死循环),不认识不限
const requeueCount = new Map()

const THRESHOLD = 80

const currentCard = computed(() => queue.value[cardIndex.value] || null)

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

async function start() {
  try {
    const res = await request.get('/vocab/due', { params: { limit: 30 } })
    queue.value = res.data.data || []
    if (!queue.value.length) {
      toast.success('今天没有到期的生词，去添加新词或直接浏览词表')
      emit('exit')
      return
    }
    cardIndex.value = 0
    flipped.value = false
    sessionDone.value = false
    sessionCount.value = { known: 0, fuzzy: 0, unknown: 0 }
    requeueCount.clear()
  } catch (err) {
    emit('exit')
  }
}

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
  // 双重守卫:飞出动画窗口(flyDir)+ 在途请求锁(grading)——快速双击"认识"或
  // 连按两下数字键,两个 grade 都会在 POST 前通过 flyDir 守卫,造成同卡双发、
  // sessionCount 双计、cardIndex 连跳两张、"不认识"回队重复入列
  if (flyDir.value || grading.value) return
  if (!currentCard.value) return
  grading.value = true
  justDragged = false // 触屏拖拽若未派生 click，标志残留会吞掉下一张卡的首次点击
  try {
    try {
      await request.post(`/vocab/${currentCard.value.id}/review`, { result })
    } catch (err) {}
    const card = currentCard.value
    sessionCount.value[result] += 1
    // —— 会话内随机回队 ——
    // 用户实测:"模糊"后续不再出现、"不认识"只在队尾出现一次,间隔拉得过开。
    // 模糊:随机插到后面 1 次(每卡每会话限一次,防模糊死循环);
    // 不认识:随机插 2 份拉开间隔,再次判不认识仍会再插,直到全会(原哲学保留)。
    if (result === 'fuzzy' || result === 'unknown') {
      const counts = requeueCount.get(card.id) || { fuzzy: 0, unknown: 0 }
      if ((counts[result] || 0) < (result === 'fuzzy' ? 1 : 99)) {
        counts[result] = (counts[result] || 0) + 1
        requeueCount.set(card.id, counts)
        reinsertRandom(card, result === 'unknown' ? 2 : 1)
      } else if (result === 'unknown') {
        // 不认识达到上限仍不认识:排到队尾兜底,直到全会
        queue.value.push(card)
      }
    }
    flipped.value = false
    ctxHits.value = []
    ctxLoading.value = false
    if (cardIndex.value + 1 >= queue.value.length) {
      sessionDone.value = true
      emit('done')
    } else {
      cardIndex.value += 1
    }
  } finally {
    grading.value = false
  }
}

/**
 * 把卡片随机插回队列后半段(当前位置至少隔一张,防"刚判完又立刻出现")。
 * Math.random 注入仅供测试。
 */
function reinsertRandom(card, copies, rng = Math.random) {
  for (let i = 0; i < copies; i++) {
    const len = queue.value.length
    const minPos = cardIndex.value + 2
    if (len < minPos) {
      queue.value.push(card)
      continue
    }
    const pos = minPos + Math.floor(rng() * (len - minPos + 1))
    queue.value.splice(Math.min(pos, len), 0, card)
  }
}

const MASTERY_LABELS = ['生词', 'L1', 'L2', 'L3', 'L4', '已掌握', '已掌握', '已掌握', '已掌握']

function masteryLabel(level) {
  return MASTERY_LABELS[level] || `L${level}`
}

// 闪卡键盘流：空格翻面，1/2/3 = 不认识/模糊/认识
function onKeydown(event) {
  if (sessionDone.value) return
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  if (event.key === ' ') {
    event.preventDefault()
    flipped.value = !flipped.value
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    // 方向键判分与按钮同语义：必须先翻面看过答案（B4）
    if (flipped.value) flyGrade('known')
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    if (flipped.value) flyGrade('unknown')
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (flipped.value) flyGrade('fuzzy')
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

// 父页在 keep-alive 里： activated/deactivated 钩子会沿子树级联到本组件，
// window 键盘监听必须跟着页面缓存起停，否则在别的页面按空格/方向键会静默推进闪卡。
// addEventListener 对同一函数引用幂等，重复 add 无副作用。
onMounted(() => {
  start()
  window.addEventListener('keydown', onKeydown)
})
onActivated(() => window.addEventListener('keydown', onKeydown))
onDeactivated(() => window.removeEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="flash-zone card card-pad">
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
          <UiButton variant="outline" @click="start">再来一轮</UiButton>
          <UiButton variant="ghost" @click="emit('exit')">返回词表</UiButton>
        </div>
      </div>
    </template>
    <template v-else-if="currentCard">
      <div class="flash-head">
        <span class="count-tip">{{ cardIndex + 1 }} / {{ queue.length }}</span>
        <UiTag size="sm" :color="currentCard.mastery_level >= 5 ? 'var(--green)' : 'var(--gold)'">
          {{ masteryLabel(currentCard.mastery_level) }}
        </UiTag>
        <UiButton size="sm" variant="ghost" @click="emit('exit')">退出</UiButton>
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
</template>

<style scoped>
/* 闪卡（样式自 VocabView 原样搬入，scoped 不跨组件边界） */
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
</style>
