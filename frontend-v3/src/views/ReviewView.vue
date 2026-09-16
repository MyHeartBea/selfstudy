<!--
  ReviewView —— 今日复习 · 砚台
  ---------------------------------------------------------------------------
  语义映射：待复习量 = 墨量；每次作答 = 落笔；掌握度 = 墨色沉淀。

  三条交互要求（对照 v2 的真实痛点设计）：
   1. **键盘流**：空格/回车看答案，1-4 选选项，方向键换题。复习是高频动作，
      手不离键盘才走得下去。
   2. **大点击区**：整张卡可点（沿用 InkCard 的教训），选项是整行可点。
   3. **不编造进度**：提交中只显示"落笔中"，不显示假百分比。

  契约：/api/reviews/today 返回 { items, dueTotal, remaining, dailyLimit, reviewedToday }；
  提交走 POST /api/mistakes/{id}/review { result, note, user_answer }。
  所有请求经 core/api，不在本文件写 URL。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { usePageMotion } from '../design/usePageMotion'

import { reviewsApi } from '../core/api'
import { toast } from '../ui/toast'
import InkDot from '../ui/InkDot.vue'
import StarRow from '../ui/StarRow.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiTag from '../ui/UiTag.vue'
import MathText from '../components/MathText.vue'

const pageRoot = ref(null)
const loading = ref(true)
const error = ref('')
const queue = ref([])
const info = ref(null) // { dueTotal, remaining, dailyLimit, reviewedToday }
const index = ref(0)
const revealed = ref(false)
const picked = ref('')
const submitting = ref(false)

const current = computed(() => queue.value[index.value] || null)
const total = computed(() => queue.value.length)
const doneCount = computed(() => index.value)
/** 墨量：今日剩余 / 配额（用于左侧墨柱高度） */
const inkRatio = computed(() => {
  const limit = info.value?.dailyLimit || total.value || 1
  const remaining = Math.max(total.value - doneCount.value, 0)
  return Math.min(100, Math.round((remaining / limit) * 100))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await reviewsApi.today()
    // 兼容两种形状：新格式是对象（带配额信息），旧格式是纯数组
    if (Array.isArray(data)) {
      queue.value = data
      info.value = null
    } else {
      queue.value = data?.items || []
      info.value = data || null
    }
    index.value = 0
    revealed.value = false
    picked.value = ''
  } catch (e) {
    error.value = e?.message || '无法载入今日星表'
  } finally {
    loading.value = false
  }
}

/** 选项行：整行可点 + 键盘 1-4 */
function choose(letter) {
  if (!current.value || current.value.question_type !== 'choice') return
  picked.value = letter
}

/** 判分：优先用后端返回的 correct_answer 做本地比对；没有答案则交给用户自评 */
function isCorrect() {
  const ans = String(current.value?.correct_answer || '')
    .trim()
    .toUpperCase()
  if (!ans || !picked.value) return null
  return ans === picked.value.toUpperCase()
}

async function submit(selfResult) {
  if (!current.value || submitting.value) return
  submitting.value = true
  // 自评优先：没有标准答案时必须由用户判断；有答案但用户没选也允许自评
  let correct = selfResult
  if (correct === undefined) {
    const judged = isCorrect()
    correct = judged === null ? true : judged
  }
  try {
    await reviewsApi.submit(current.value.id, { correct, userAnswer: picked.value })
    // 落笔失败不阻塞复习：提示后继续走，避免一道题卡住整条队列
    next()
  } catch (e) {
    toast.error(e?.message || '落笔失败，已跳过')
    next()
  } finally {
    submitting.value = false
  }
}

function next() {
  if (index.value < total.value - 1) {
    index.value += 1
    revealed.value = false
    picked.value = ''
  } else {
    index.value = total.value
    revealed.value = false
    picked.value = ''
  }
}

function prev() {
  if (index.value > 0) {
    index.value -= 1
    revealed.value = false
    picked.value = ''
  }
}

/** 键盘流：空格/回车看答案 - 1-4 选项 - Enter 落笔 - 方向键换题 */
function onKey(e) {
  if (e.metaKey || e.ctrlKey || e.altKey) return
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return

  if (e.key === ' ') {
    e.preventDefault()
    revealed.value = true
    return
  }
  if (e.key === 'Enter') {
    e.preventDefault()
    if (!revealed.value) revealed.value = true
    else submit()
    return
  }
  if (['1', '2', '3', '4'].includes(e.key)) {
    choose(String.fromCharCode(64 + Number(e.key)))
    return
  }
  if (e.key === 'ArrowRight') {
    e.preventDefault()
    next()
  }
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prev()
  }
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))

/** 页面级动效：错峰入场 + 视差 + 磁吸 + 路径描绘（见 design/usePageMotion） */
usePageMotion(pageRoot, { stagger: 55 })
</script>

<template>
  <main ref="pageRoot" id="main" class="verse">
    <header class="head">
      <span class="mono">[01] VERSE · 今日复习</span>
      <span class="mono">
        {{ info ? `配额 ${info.reviewedToday || 0} / ${info.dailyLimit || total}` : `${total} 题` }}
      </span>
    </header>

    <!-- 左：墨量柱 -->
    <aside class="well-col reveal" aria-hidden="true" data-reveal>
      <span class="mono wlab">墨量</span>
      <div class="well">
        <i class="fill" :style="{ height: inkRatio + '%' }"></i>
        <span class="tick t25"></span><span class="tick t50"></span><span class="tick t75"></span>
      </div>
      <span class="mono wnum">{{ Math.max(total - doneCount, 0) }}</span>
      <span class="mono wsub">剩余</span>
    </aside>

    <section class="stage reveal" data-reveal>
      <UiEmpty v-if="loading" variant="skeleton" thumb :rows="3" />

      <UiEmpty v-else-if="error" title="星表载入失败" :hint="error">
        <template #action>
          <UiButton variant="solid" @click="load">重试</UiButton>
        </template>
      </UiEmpty>

      <UiEmpty
        v-else-if="!current"
        title="今晚没有待复习"
        :hint="
          info
            ? `已复习 ${info.reviewedToday || 0} 题，配额 ${info.dailyLimit || 0} 题`
            : '可以去录入一道题，或提前看明天的星表'
        "
      >
        <template #action>
          <UiButton variant="solid" @click="load">刷新星表</UiButton>
        </template>
      </UiEmpty>

      <article v-else class="paper" tabindex="0">
        <div class="meta">
          <UiTag tone="vein" size="sm">{{
            current.question_type === 'choice' ? '选择题' : '题目'
          }}</UiTag>
          <span class="mono src">{{ current.source || '未标注来源' }}</span>
          <span class="mono idx">{{ doneCount + 1 }} / {{ total }}</span>
        </div>

        <h1 class="q"><MathText :text="current.question" /></h1>

        <ul v-if="current.question_type === 'choice'" class="opts">
          <li
            v-for="(text, i) in [
              current.option_a,
              current.option_b,
              current.option_c,
              current.option_d,
            ]"
            :key="i"
            :class="{ on: picked === String.fromCharCode(65 + i) }"
          >
            <button
              type="button"
              class="opt"
              :aria-pressed="picked === String.fromCharCode(65 + i)"
              @click="choose(String.fromCharCode(65 + i))"
            >
              <span class="letter mono">{{ String.fromCharCode(65 + i) }}</span>
              <span class="otext"><MathText :text="text || '（空）'" /></span>
            </button>
          </li>
        </ul>

        <!-- 答案区：空格揭示，揭示前不泄漏 -->
        <div class="ans" :class="{ shown: revealed }">
          <template v-if="revealed">
            <p class="mono alab">标准答案</p>
            <p class="aval"><MathText :text="current.correct_answer || '（未录入）'" /></p>
            <p v-if="current.analysis" class="anote">{{ current.analysis }}</p>
          </template>
          <p v-else class="mono hint">按 空格 看答案 · 1-4 选选项 · Enter 落笔 · 方向键换题</p>
        </div>

        <div class="ops">
          <UiButton variant="solid" :loading="submitting" @click="submit()">
            {{ submitting ? '落笔中' : '落笔（Enter）' }}
          </UiButton>
          <UiButton v-if="revealed" @click="submit(false)">没记住</UiButton>
          <UiButton variant="quiet" @click="prev">上一题</UiButton>
          <UiButton variant="quiet" @click="next">跳过</UiButton>
          <span class="dots">
            <InkDot :value="Math.min(doneCount, 5)" label="本次进度" />
            <StarRow :value="current.review_count || 0" :max="7" label="复习遍数" />
          </span>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.verse {
  position: relative;
  z-index: var(--z-content);
  max-width: var(--col);
  margin: 0 auto;
  padding: clamp(84px, 12vh, 132px) var(--pad) 70px;
  display: grid;
  grid-template-columns: clamp(74px, 8vw, 104px) minmax(0, 1fr);
  gap: clamp(16px, 2.6vw, 40px);
  align-items: start;
}
.head {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
  margin-bottom: clamp(16px, 3vh, 30px);
}

/* 墨量柱 */
.well-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 9px;
  position: sticky;
  top: 90px;
}
.well {
  position: relative;
  width: 100%;
  height: clamp(120px, 26vh, 200px);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--sky-1);
  overflow: hidden;
}
.fill {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(180deg, var(--ink-1), var(--ink-0));
  transition: height 0.9s var(--e-settle);
}
.tick {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: var(--line);
}
.t25 {
  top: 25%;
}
.t50 {
  top: 50%;
}
.t75 {
  top: 75%;
}
.wnum {
  font-size: 20px;
  color: var(--ink-0);
}
.wsub {
  color: var(--ink-3);
}

/* 纸面 */
.paper {
  padding: clamp(20px, 3vw, 36px);
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.paper:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}
.meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 15px;
}
.src {
  color: var(--ink-3);
}
.idx {
  margin-left: auto;
  color: var(--ink-2);
}
.q {
  font-size: clamp(1.15rem, 2vw, 1.6rem);
  font-weight: 500;
  line-height: 1.6;
  letter-spacing: -0.01em;
  margin-bottom: 18px;
}

.opts {
  list-style: none;
  display: grid;
  gap: 8px;
  margin-bottom: 18px;
}
.opt {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  text-align: left;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    border-color 0.22s var(--e-settle),
    background 0.22s var(--e-settle);
}
.opt:hover {
  border-color: var(--ink-3);
}
.opt[aria-pressed='true'] {
  border-color: var(--redshift);
  background: oklch(0.665 0.196 34 / 0.1);
}
.letter {
  color: var(--ink-2);
  padding-top: 1px;
}
.opt[aria-pressed='true'] .letter {
  color: var(--redshift);
}
.otext {
  line-height: 1.65;
}

.ans {
  min-height: 78px;
  padding: 14px 16px;
  border-left: 2px solid var(--line-strong);
  background: var(--sky-0);
  border-radius: var(--radius);
  margin-bottom: 18px;
}
.ans.shown {
  border-left-color: var(--redshift);
}
.alab {
  color: var(--ink-3);
  margin-bottom: 5px;
}
.aval {
  font-size: var(--fs-h2);
  font-weight: 500;
  color: var(--redshift);
}
.anote {
  margin-top: 9px;
  color: var(--ink-1);
  font-size: var(--fs-sm);
  line-height: 1.8;
}
.hint {
  color: var(--ink-3);
}

.ops {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.dots {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}

@media (max-width: 820px) {
  .verse {
    grid-template-columns: 1fr;
  }
  .well-col {
    position: static;
    flex-direction: row;
    align-items: center;
  }
  .well {
    width: 60px;
    height: 60px;
  }
  .dots {
    margin-left: 0;
  }
}
</style>
