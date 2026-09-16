<!--
  PracticeView —— 自主练习
  ---------------------------------------------------------------------------
  语义：自主练习 = 不受配额约束的自由观测（复习页是"今晚的观测清单"，这里是"随便看看"）。

  契约（基线实测）：
    GET  /api/reviews/practice?limit=N      - **裸数组**（题目列表）
    GET  /api/reviews/practice/mock?limit=N - **裸数组**
    GET  /api/approaches                    - **[字符串数组]**（套路模板）
  注意两个 practice 端点都返回裸数组，不是分页对象 —— v2 的 ReviewView 两种都接受，
  这里统一按数组处理，并在拿到分页对象时兜底取 items。

  设计取舍：练习页不写回复习进度（那是复习页的职责），所以这里只做"出题 / 看答案 / 下一题"，
  不调用提交接口 —— 避免用户在"随便看看"时误改复习阶梯。
-->
<script setup>
import { computed, onMounted, ref } from 'vue'

import { practiceApi, subjectProfileApi } from '../core/api/extra'
import { toast } from '../ui/toast'
import { usePageMotion } from '../design/usePageMotion'
import InkDot from '../ui/InkDot.vue'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTag from '../ui/UiTag.vue'

const pageRoot = ref(null)
usePageMotion(pageRoot, { stagger: 55 })

const loading = ref(true)
const errorText = ref('')
const queue = ref([])
const index = ref(0)
const revealed = ref(false)
const size = ref('10')
const mode = ref('practice') // practice | mock

const approaches = ref([])

const SIZES = [
  { value: '5', label: '5 题' },
  { value: '10', label: '10 题' },
  { value: '20', label: '20 题' },
  { value: '30', label: '30 题' },
]

const current = computed(() => queue.value[index.value] || null)
const done = computed(() => index.value >= queue.value.length)
const progressText = computed(() =>
  queue.value.length
    ? `${Math.min(index.value + 1, queue.value.length)} / ${queue.value.length}`
    : '—',
)

/** 两个 practice 端点都返回裸数组，这里同时兜底分页对象 */
function toList(data) {
  if (Array.isArray(data)) return data
  return data?.items || []
}

async function load() {
  loading.value = true
  errorText.value = ''
  index.value = 0
  revealed.value = false
  try {
    const limit = Number(size.value) || 10
    const data =
      mode.value === 'mock' ? await practiceApi.mock(limit) : await practiceApi.practice(limit)
    queue.value = toList(data)
    if (!queue.value.length) toast.info('没有可练习的题目')
  } catch (e) {
    errorText.value = e?.message || '无法载入练习题'
    queue.value = []
  } finally {
    loading.value = false
  }
}

function next() {
  if (index.value < queue.value.length) {
    index.value += 1
    revealed.value = false
  }
}
function prev() {
  if (index.value > 0) {
    index.value -= 1
    revealed.value = false
  }
}

function onKey(e) {
  const tag = (e.target?.tagName || '').toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (e.key === ' ') {
    e.preventDefault()
    revealed.value = true
  } else if (e.key === 'Enter' || e.key === 'ArrowRight') {
    e.preventDefault()
    next()
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prev()
  }
}

onMounted(async () => {
  load()
  try {
    approaches.value = (await subjectProfileApi.approaches()) || []
  } catch {
    approaches.value = []
  }
  window.addEventListener('keydown', onKey)
})
</script>

<template>
  <main id="main" ref="pageRoot" class="pad">
    <header class="head">
      <span class="mono">[12] FREE STUDY · 自主练习</span>
      <span class="mono">{{ progressText }}</span>
    </header>

    <div class="tools reveal" data-reveal>
      <UiSelect
        v-model="mode"
        :options="[
          { value: 'practice', label: '常规练习（按薄弱度）' },
          { value: 'mock', label: '模考式（随机抽题）' },
        ]"
        label="模式"
        @change="load"
      />
      <UiSelect v-model="size" :options="SIZES" label="题量" @change="load" />
      <UiButton variant="solid" @click="load">换一批</UiButton>
    </div>

    <p class="note mono reveal" data-reveal>
      练习页<b>不写回复习进度</b>——那是复习页的职责。这里只出题看答案，
      不会改动题目的复习阶梯，所以可以放心"随便看看"。
    </p>

    <UiEmpty v-if="loading" variant="skeleton" thumb :rows="3" />
    <UiEmpty v-else-if="errorText" title="载入失败" :hint="errorText">
      <template #action><UiButton variant="solid" @click="load">重试</UiButton></template>
    </UiEmpty>
    <UiEmpty v-else-if="done" title="这一批练完了" :hint="`共 ${queue.length} 题`">
      <template #action><UiButton variant="solid" @click="load">再来一批</UiButton></template>
    </UiEmpty>

    <article v-else-if="current" class="paper reveal" data-reveal>
      <div class="meta">
        <UiTag tone="violet" size="sm">
          {{ current.question_type === 'choice' ? '选择题' : '题目' }}
        </UiTag>
        <span class="mono src">{{ current.source || '未标注来源' }}</span>
        <span class="mono idx">{{ index + 1 }} / {{ queue.length }}</span>
      </div>

      <h2 class="q">{{ current.question }}</h2>

      <ul v-if="current.question_type === 'choice'" class="opts">
        <li
          v-for="(text, i) in [
            current.option_a,
            current.option_b,
            current.option_c,
            current.option_d,
          ]"
          :key="i"
        >
          <span class="mono l">{{ String.fromCharCode(65 + i) }}</span
          >{{ text || '（空）' }}
        </li>
      </ul>

      <div class="ans" :class="{ shown: revealed }">
        <template v-if="revealed">
          <span class="mono lab">标准答案</span>
          <p class="av">{{ current.correct_answer || '（未录入）' }}</p>
          <p v-if="current.analysis" class="an">{{ current.analysis }}</p>
        </template>
        <p v-else class="mono hint">按 空格 看答案 · Enter / 方向键 换题</p>
      </div>

      <div class="ops">
        <UiButton variant="solid" @click="revealed = true">看答案（空格）</UiButton>
        <UiButton variant="quiet" @click="prev">上一题</UiButton>
        <UiButton variant="quiet" @click="next">下一题（Enter）</UiButton>
        <span class="dots">
          <InkDot :value="Math.min(Math.round((current.difficulty || 0) * 1), 5)" label="难度" />
        </span>
      </div>
    </article>

    <section v-if="approaches.length" class="chips-wrap reveal" data-reveal>
      <span class="mono lab">可用套路（录入时可直接引用）</span>
      <div class="chips">
        <UiTag v-for="(a, i) in approaches" :key="i" tone="gold" size="sm">{{ a }}</UiTag>
      </div>
    </section>
  </main>
</template>

<style scoped>
.pad {
  position: relative;
  z-index: var(--z-content);
  max-width: 880px;
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
.tools {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) auto;
  gap: 14px;
  align-items: end;
  margin-bottom: 14px;
}
.note {
  color: var(--ink-2);
  line-height: 1.8;
  margin-bottom: clamp(16px, 3vh, 28px);
}
.note b {
  color: var(--ink-0);
  font-weight: 500;
}

.paper {
  padding: clamp(20px, 3vw, 34px);
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
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
  font-size: clamp(1.1rem, 1.9vw, 1.5rem);
  font-weight: 500;
  line-height: 1.65;
  margin-bottom: 18px;
}
.opts {
  list-style: none;
  display: grid;
  gap: 8px;
  margin-bottom: 18px;
}
.opts li {
  padding: 11px 14px;
  background: var(--sky-0);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  line-height: 1.65;
}
.opts .l {
  margin-right: 9px;
  color: var(--ink-2);
}
.ans {
  min-height: 74px;
  padding: 14px 16px;
  border-left: 2px solid var(--line-strong);
  background: var(--sky-0);
  border-radius: var(--radius);
  margin-bottom: 18px;
}
.ans.shown {
  border-left-color: var(--violet);
}
.lab {
  color: var(--ink-3);
}
.av {
  font-size: var(--fs-h2);
  font-weight: 500;
  color: var(--violet);
  margin-top: 5px;
}
.an {
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
}
.chips-wrap {
  margin-top: clamp(22px, 4vh, 40px);
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 820px) {
  .tools {
    grid-template-columns: 1fr;
  }
}
</style>
