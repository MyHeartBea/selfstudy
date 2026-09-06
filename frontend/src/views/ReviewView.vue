<script setup>
/** 复习/练习流程：今日队列与四种练习模式共用，按题型给出作答组件 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import request from '../api/request'
import ChoiceAnswer from '../components/ChoiceAnswer.vue'
import FillAnswer from '../components/FillAnswer.vue'
import SolutionAnswer from '../components/SolutionAnswer.vue'
import MathText from '../components/MathText.vue'
import MistakeMeta from '../components/MistakeMeta.vue'
import QuestionImages from '../components/QuestionImages.vue'
import { toast } from '../ui/toast'
import { confirmDialog } from '../ui/confirm'
import { confetti } from '../utils/confetti'
import { scoreLetters } from '../utils/examScoring'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import Icon from '../ui/Icon.vue'
import GlassCard from '../ui/GlassCard.vue'
import StageBadge from '../ui/StageBadge.vue'
import Skeleton from '../ui/Skeleton.vue'
import RingProgress from '../ui/RingProgress.vue'

const router = useRouter()
const route = useRoute()
const queue = ref([])
const index = ref(0)
const loading = ref(false)
const selected = ref(null)
const answered = ref(false)
const revealed = ref(false)
const userInput = ref('')
const judging = ref(false)
const grading = ref(false)
const judgeResult = ref(null)
const gradeResult = ref(null)
const submitting = ref(false)
const done = ref(false)
const reviewSaved = ref(false)
const resultCount = ref({ correct: 0, wrong: 0 })

const current = computed(() => queue.value[index.value] || null)
const practiceMode = computed(() => String(route.query.mode || ''))
const isPractice = computed(() =>
  ['curve', 'wrong_time', 'random', 'real_exam', 'mock'].includes(practiceMode.value),
)
const practiceTitle = computed(
  () =>
    ({
      curve: '记忆曲线练习',
      wrong_time: '按错误时间练习',
      random: '随机抽题',
      real_exam: '真题专项',
      mock: '真题模考',
    }[practiceMode.value] || ''),
)
const emptyText = computed(() =>
  isPractice.value ? '没有符合条件的错题，换个条件试试' : '暂无待复习错题',
)
const questionType = computed(
  () => current.value?.question_type || 'choice',
)
const isChoice = computed(() => ['choice', 'multi'].includes(questionType.value))
const isMulti = computed(() => questionType.value === 'multi')
const isFill = computed(() => questionType.value === 'fill')
const isTranslation = computed(() => questionType.value === 'translation')
const isSolution = computed(() => questionType.value === 'solution')
const progress = computed(() =>
  queue.value.length ? Math.round((index.value / queue.value.length) * 100) : 0,
)

// —— 戏台汉字数字：壹、贰、叁…（超过拾用阿拉伯数字） ——
const CN_NUMERALS = ['壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖', '拾']
const stageNumeral = computed(() =>
  index.value < CN_NUMERALS.length ? CN_NUMERALS[index.value] : String(index.value + 1),
)

// —— 真题模考：倒计时 + 作答暂存 + 交卷统一判分 ——
const isMock = computed(() => practiceMode.value === 'mock')
const mockDuration = computed(() => Math.min(240, Math.max(5, Number(route.query.duration) || 60)))
const mockAnswers = ref({})
const mockLeft = ref(0)
const mockSubmitting = ref(false)
const mockReport = ref(null)
let mockTimer = 0

const mockClock = computed(() => {
  const s = mockLeft.value
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${String(m).padStart(2, '0')}:${ss}`
})

function stopMockTimer() {
  if (mockTimer) {
    clearInterval(mockTimer)
    mockTimer = 0
  }
}

function startMockTimer() {
  stopMockTimer()
  const deadline = Date.now() + mockDuration.value * 60000
  mockLeft.value = mockDuration.value * 60
  mockTimer = setInterval(() => {
    mockLeft.value = Math.max(0, Math.round((deadline - Date.now()) / 1000))
    if (mockLeft.value <= 0) {
      stopMockTimer()
      toast.warning('考试时间到，已自动交卷')
      submitMock(true)
    }
  }, 1000)
}

const mockOptionList = computed(() => {
  if (!current.value) return []
  return ['A', 'B', 'C', 'D']
    .map((key) => ({ key, text: current.value['option_' + key.toLowerCase()] }))
    .filter((o) => o.text)
})

function mockPick(key) {
  const q = current.value
  if (!q) return
  const cur = String(mockAnswers.value[q.id] || '')
  if (q.question_type === 'multi') {
    const set = new Set(cur.split('').filter(Boolean))
    set.has(key) ? set.delete(key) : set.add(key)
    mockAnswers.value[q.id] = [...set].sort().join('')
  } else {
    mockAnswers.value[q.id] = key
  }
}

function mockPicked(key) {
  const q = current.value
  return q ? String(mockAnswers.value[q.id] || '').includes(key) : false
}

function fmtDuration(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
}

async function submitMock(auto = false) {
  if (!isMock.value || mockSubmitting.value || done.value || !queue.value.length) return
  if (!auto) {
    const unanswered = queue.value.filter((q) => !String(mockAnswers.value[q.id] || '').trim())
    const okToGo = await confirmDialog({
      title: '交卷确认',
      message: unanswered.length
        ? `还有 ${unanswered.length} 题未作答，交卷后未作答按错误计。`
        : `共 ${queue.value.length} 题，确认交卷？`,
      confirmText: '交卷',
    })
    if (!okToGo) return
  }
  stopMockTimer()
  mockSubmitting.value = true
  try {
    let correct = 0
    const details = []
    for (const q of queue.value) {
      const ans = String(mockAnswers.value[q.id] || '').trim()
      let result = false
      if (q.question_type === 'fill' && ans) {
        try {
          const res = await request.post(`/mistakes/${q.id}/judge`, { user_answer: ans })
          result = !!res.data.data?.correct
        } catch (err) {
          result = false
        }
      } else if (q.question_type === 'multi') {
        result = scoreLetters(ans, q.correct_answer)
      } else {
        result = scoreLetters(ans, q.correct_answer)
      }
      if (result) correct += 1
      // 每题结果计入复习记录（SM-2 调度），模考即复习
      await request.post(`/mistakes/${q.id}/review`, { result, user_answer: ans })
      details.push({
        id: q.id,
        snippet: (q.question || '').slice(0, 64),
        your: ans || '（未作答）',
        right: q.correct_answer || '',
        result,
      })
    }
    resultCount.value.correct = correct
    resultCount.value.wrong = queue.value.length - correct
    mockReport.value = {
      total: queue.value.length,
      correct,
      score: Math.round((correct / Math.max(1, queue.value.length)) * 100),
      usedSec: mockDuration.value * 60 - mockLeft.value,
      overtime: auto === true,
      details: details.filter((d) => !d.result),
    }
    done.value = true
    window.dispatchEvent(new CustomEvent('km:review-saved'))
    // 成绩存档（统计页绘制模考趋势；失败静默——复习记录已提交不受影响）
    request
      .post('/mocks', {
        exam_year: String(route.query.source_year || ''),
        total: mockReport.value.total,
        correct: mockReport.value.correct,
        score: mockReport.value.score,
        duration_min: mockDuration.value,
        used_seconds: mockReport.value.usedSec,
      })
      .catch(() => {})
    setTimeout(() => confetti.celebrate({ count: 40 }), 250)
  } catch (err) {
    toast.error('交卷失败，请重试')
  } finally {
    mockSubmitting.value = false
  }
}

async function loadQueue() {
  loading.value = true
  try {
    let res
    if (isPractice.value) {
      const params = {
        mode: practiceMode.value,
        count: Number(route.query.count) || 10,
      }
      if (route.query.subject_id) params.subject_id = route.query.subject_id
      if (route.query.sub_subject_id) params.sub_subject_id = route.query.sub_subject_id
      if (route.query.question_type) params.question_type = route.query.question_type
      if (route.query.difficulty) params.difficulty = route.query.difficulty
      if (route.query.tag) params.tag = route.query.tag
      if (route.query.search) params.search = route.query.search
      if (route.query.source_type) params.source_type = route.query.source_type
      if (route.query.source_year) params.source_year = route.query.source_year
      if (route.query.mistake_id) params.mistake_id = route.query.mistake_id
      res = await request.get('/reviews/practice', { params })
    } else {
      res = await request.get('/reviews/today')
    }
    queue.value = res.data.data || []
    if (isMock.value) {
      // 模考仅含客观题（选择/多选/填空），主观题与英语整篇不进卷面
      queue.value = queue.value.filter(
        (q) => ['choice', 'multi', 'fill'].includes(q.question_type) && !q.passage_text,
      )
    }
    if (!queue.value.length) done.value = !isPractice.value
    if (isMock.value && queue.value.length) startMockTimer()
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function confirmAnswer() {
  if (!selected.value) return
  answered.value = true
  submitReview(selected.value === current.value.correct_answer, false)
}

async function submitFill() {
  if (!current.value) return
  if (!userInput.value.trim()) {
    toast.warning('请输入你的答案')
    return
  }
  judging.value = true
  try {
    const res = await request.post(`/mistakes/${current.value.id}/judge`, {
      user_answer: userInput.value,
    })
    judgeResult.value = res.data.data
    revealed.value = true
    await submitReview(judgeResult.value.correct, false)
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    judging.value = false
  }
}

async function submitSolution() {
  if (!current.value) return
  if (!userInput.value.trim()) {
    toast.warning('请写下你的解答过程')
    return
  }
  grading.value = true
  try {
    const res = await request.post(`/mistakes/${current.value.id}/grade`, {
      user_answer: userInput.value,
    })
    gradeResult.value = res.data.data
    revealed.value = true
  } catch (err) {
    // 错误提示由请求拦截器统一处理
  } finally {
    grading.value = false
  }
}

/** 翻译题：提交后展示参考译文对照，等待自评（不调后端判分）。 */
function submitTranslation() {
  if (!current.value) return
  if (!userInput.value.trim()) {
    toast.warning('请先写下你的译文')
    return
  }
  judgeResult.value = { correct: null, translation: true }
  revealed.value = true
}

async function next() {
  if (!current.value) return
  const result = selected.value === current.value.correct_answer
  await submitReview(result, true)
}

function nextFill() {
  if (!judgeResult.value) return
  submitReview(judgeResult.value.correct, true)
}

async function submitReview(result, advance = true) {
  if (!current.value) return
  if (!reviewSaved.value) {
    submitting.value = true
    try {
      await request.post(`/mistakes/${current.value.id}/review`, {
        result,
        user_answer: userInput.value,
      })
      toast.success('复习记录已保存')
      // 通知侧边栏进度环刷新
      window.dispatchEvent(new CustomEvent('km:review-saved'))
      if (result) {
        resultCount.value.correct += 1
        // 答对的小庆祝：从"保存"按钮附近迸发
        const anchor = document.querySelector('.review-footer')
        if (anchor) confetti.burstAtElement(anchor, { count: 18, power: 6 })
      } else {
        resultCount.value.wrong += 1
      }
      reviewSaved.value = true
    } catch (err) {
      // 错误提示由请求拦截器统一处理
      return
    } finally {
      submitting.value = false
    }
  }
  if (advance) {
    index.value += 1
    selected.value = null
    answered.value = false
    revealed.value = false
    userInput.value = ''
    judgeResult.value = null
    gradeResult.value = null
    reviewSaved.value = false
    if (index.value >= queue.value.length) {
      done.value = true
      // 全部完成：双侧礼花庆祝
      setTimeout(() => confetti.celebrate({ count: 46 }), 250)
    }
  }
}

onMounted(loadQueue)

// —— 键盘快捷键：1-4/A-D 选选项、Enter 确认/下一题、空格看答案 ——
const KEY_TO_OPTION = { '1': 'A', '2': 'B', '3': 'C', '4': 'D', a: 'A', b: 'B', c: 'C', d: 'D' }

function onKeydown(event) {
  if (done.value || !current.value || loading.value) return
  // 输入框聚焦时不拦截（填空/翻译/解答题作答中）
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    // Ctrl+Enter 提交填空/翻译/解答
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      if (isFill.value && !judgeResult.value) submitFill()
      else if (isTranslation.value && !judgeResult.value) submitTranslation()
      else if (isSolution.value && !gradeResult.value) submitSolution()
    }
    return
  }
  const key = event.key.toLowerCase()

  // 模考：数字键作答、Enter 翻题，不即时判分
  if (isMock.value) {
    if (isChoice.value && KEY_TO_OPTION[key]) {
      mockPick(KEY_TO_OPTION[key])
      event.preventDefault()
      return
    }
    if (event.key === 'Enter') {
      if (index.value < queue.value.length - 1) index.value += 1
      else submitMock(false)
      event.preventDefault()
    }
    return
  }

  if (isChoice.value) {
    if (!answered.value) {
      if (KEY_TO_OPTION[key]) {
        const letter = KEY_TO_OPTION[key]
        if (isMulti.value) {
          // 多选：数字/字母键切换勾选
          const set = new Set((selected.value || '').split('').filter(Boolean))
          set.has(letter) ? set.delete(letter) : set.add(letter)
          selected.value = [...set].sort().join('')
        } else {
          selected.value = letter
        }
        event.preventDefault()
      } else if (event.key === 'Enter' && selected.value) {
        confirmAnswer()
        event.preventDefault()
      }
    } else if (event.key === 'Enter' && reviewSaved.value) {
      next()
      event.preventDefault()
    }
    return
  }

  if (isTranslation.value) {
    if (judgeResult.value) {
      if (event.key === 'Enter' || key === 'q') submitReview(true, true)
      else if (key === 'w') submitReview(false, true)
    }
    return
  }

  if (isFill.value) {
    if (judgeResult.value && event.key === 'Enter') {
      nextFill()
      event.preventDefault()
    } else if (judgeResult.value && key === 'q') {
      submitReview(true, true)
    } else if (judgeResult.value && key === 'w') {
      submitReview(false, true)
    }
    return
  }

  if (isSolution.value) {
    if (gradeResult.value && event.key === 'Enter') {
      const correct = gradeResult.value.score >= 60
      submitReview(correct, true)
    }
    return
  }

  // 通用题型：空格显示答案，Q/W 记住/没记住
  if (!revealed.value && event.key === ' ') {
    revealed.value = true
    event.preventDefault()
  } else if (revealed.value && key === 'q') {
    submitReview(true, true)
  } else if (revealed.value && key === 'w') {
    submitReview(false, true)
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  stopMockTimer()
})
</script>

<template>
  <div class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Review Flow</div>
        <h2>{{ practiceTitle || '今日复习' }}</h2>
        <p class="view-desc">按记忆节奏完成复习，只做当前最该做的题。</p>
      </div>
      <div class="header-actions">
        <UiButton v-if="isPractice" variant="outline" @click="router.push('/practice')">
          重新选题
        </UiButton>
        <span v-if="isMock && !done" class="mock-timer num" :class="{ danger: mockLeft <= 300 }">
          <Icon name="clock" :size="14" />
          {{ mockClock }}
        </span>
        <span class="count-tip remaining">待复习 {{ Math.max(0, queue.length - index) }} 题</span>
      </div>
    </div>

    <!-- 模考成绩单 -->
    <template v-if="done && mockReport">
      <GlassCard class="stage-card" :hover="false">
        <template #badge><StageBadge text="模考成绩单" /></template>
        <div class="mr-body">
          <RingProgress :percentage="mockReport.score">
            <div class="ring-center-text">
              <b class="num">{{ mockReport.score }} 分</b>
              <span>{{ mockReport.correct }}/{{ mockReport.total }} 正确</span>
            </div>
          </RingProgress>
          <div class="mr-stats">
            <div class="mr-line"><span>用时</span><b class="num">{{ fmtDuration(mockReport.usedSec) }}</b>
              <i v-if="mockReport.overtime" class="mr-overtime">超时自动交卷</i>
            </div>
            <div class="mr-line"><span>答对</span><b class="num mr-ok">{{ mockReport.correct }}</b></div>
            <div class="mr-line"><span>答错</span><b class="num mr-bad">{{ mockReport.total - mockReport.correct }}</b></div>
            <p class="mr-note">每题结果已计入复习记录（SM-2 自适应调度），错题将按计划再次推送。</p>
          </div>
        </div>
        <div v-if="mockReport.details.length" class="mr-wrong">
          <div class="block-label">错题回顾</div>
          <div v-for="d in mockReport.details" :key="d.id" class="mr-item">
            <p class="mr-q"><MathText :text="d.snippet + '…'" /></p>
            <p class="mr-ans">
              你的答案：<b class="mr-bad">{{ d.your }}</b>
              <span class="mr-sep">·</span>
              正确答案：<b class="mr-ok">{{ d.right }}</b>
            </p>
          </div>
        </div>
        <div class="done-actions">
          <UiButton variant="primary" @click="router.push('/practice')">再来一场</UiButton>
          <UiButton variant="ghost" @click="router.push('/mistakes')">返回错题列表</UiButton>
        </div>
      </GlassCard>
    </template>

    <template v-else-if="done">
      <div class="done-stage">
        <div class="stamp">已<br />完成</div>
        <h3 class="done-title">{{ practiceTitle ? '练习完成' : '今日复习完成' }}</h3>
        <p class="done-sub">
          答对 <b class="ok pop-num">{{ resultCount.correct }}</b> 题，答错
          <b class="bad pop-num">{{ resultCount.wrong }}</b> 题 · 朱砂印为证
        </p>
        <div class="done-actions">
          <UiButton v-if="isPractice" variant="outline" @click="router.push('/practice')">再练一组</UiButton>
          <UiButton variant="primary" @click="router.push('/mistakes')">返回错题列表</UiButton>
          <UiButton variant="ghost" @click="router.push('/stats')">查看统计</UiButton>
        </div>
      </div>
    </template>

    <template v-else-if="current">
      <!-- 巨型汉字数字戏台背景（随题号翻动） -->
      <div class="stage-wrap">
        <div :key="index" class="stage-numeral serif" aria-hidden="true">{{ stageNumeral }}</div>
        <!-- 顶部流光进度线 -->
        <div class="top-progress" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
          <div class="tp-fill" :style="{ width: Math.max(3, progress) + '%' }"></div>
        </div>

      <GlassCard class="stage-card" :hover="false">
        <template #badge>
          <StageBadge :text="`第 ${index + 1} / ${queue.length} 题`" />
        </template>
        <div class="detail-meta">
          <MistakeMeta :mistake="current" />
          <span v-if="current.days_since_wrong != null" class="count-tip">
            错于 {{ current.days_since_wrong === 0 ? '今天' : current.days_since_wrong + ' 天前' }}
          </span>
          <span v-if="current.days_since_review != null" class="count-tip">
            {{ current.days_since_review === 0 ? '今天复习过' : current.days_since_review + ' 天未复习' }}
          </span>
        </div>

        <!-- 英语整篇：先给原文与参考译文，再做题 -->
        <div v-if="current.passage_text" class="review-passage">
          <div class="block-label">原文</div>
          <div class="rp-text"><MathText :text="current.passage_text" /></div>
          <details v-if="current.passage_translation" class="rp-trans">
            <summary>查看全文翻译</summary>
            <div class="rp-trans-text"><MathText :text="current.passage_translation" /></div>
          </details>
        </div>

        <div class="question-block">
          <QuestionImages :images="current.images" />
          <MathText :text="current.question" />
        </div>

        <div v-if="current.difficulty_points" class="difficulty-block">
          <span class="block-label">主要难点</span>
          <MathText :text="current.difficulty_points" />
        </div>

        <!-- 模考：暂存作答，不即时判分 -->
        <template v-if="isMock">
          <p class="mock-note">模考模式：作答不立即判分，交卷后统一判分并计入复习记录。卷面仅含客观题（单选/多选/填空）。</p>
          <template v-if="isChoice">
            <div
              v-for="opt in mockOptionList"
              :key="opt.key"
              class="option-row clickable"
              :class="{ selected: mockPicked(opt.key) }"
              @click="mockPick(opt.key)"
            >
              <span class="option-key">{{ opt.key }}</span>
              <MathText :text="opt.text || '（未填写）'" />
            </div>
            <p v-if="current.question_type === 'multi'" class="multi-hint">多选题：少选、错选均不得分</p>
          </template>
          <textarea
            v-else
            v-model="mockAnswers[current.id]"
            class="field-input"
            rows="3"
            placeholder="输入你的答案（交卷后按别名/数值容差统一判分）"
          ></textarea>
          <div class="review-footer">
            <UiButton variant="outline" :disabled="index === 0" @click="index -= 1">上一题</UiButton>
            <UiButton v-if="index < queue.length - 1" variant="primary" @click="index += 1">下一题</UiButton>
            <UiButton variant="success" :loading="mockSubmitting" @click="submitMock(false)">
              交卷（{{ Object.keys(mockAnswers).filter((k) => String(mockAnswers[k]).trim()).length }}/{{ queue.length }} 已答）
            </UiButton>
          </div>
        </template>

        <template v-else-if="isChoice">
          <ChoiceAnswer
            :current="current"
            :selected="selected"
            :answered="answered"
            :submitting="submitting"
            :review-saved="reviewSaved"
            @select="selected = $event"
            @confirm="confirmAnswer"
            @next="next"
          />
        </template>

        <template v-else-if="isTranslation">
          <template v-if="!judgeResult">
            <textarea
              v-model="userInput"
              class="field-input"
              rows="6"
              placeholder="把整段译文写在这里，提交后对照参考译文自评"
            ></textarea>
            <div class="review-footer">
              <UiButton variant="primary" size="lg" @click="submitTranslation">
                提交译文，对照参考
              </UiButton>
              <UiButton variant="outline" size="lg" @click="submitReview(true, true)">
                这段我熟，直接过
              </UiButton>
            </div>
          </template>
          <template v-else>
            <div class="answer-block">
              <div class="block-label">你的译文</div>
              <p style="margin: 0; white-space: pre-wrap">{{ userInput }}</p>
            </div>
            <div class="analysis-block">
              <div class="block-label">参考译文</div>
              <MathText :text="current.correct_answer || '暂无参考译文'" />
            </div>
            <div v-if="current.analysis" class="difficulty-block">
              <div class="block-label">笔记 / 讲解</div>
              <MathText :text="current.analysis" />
            </div>
            <div class="review-footer">
              <UiButton variant="success" size="lg" :loading="submitting" @click="submitReview(true, true)">
                译对了
              </UiButton>
              <UiButton variant="outline" size="lg" :loading="submitting" @click="submitReview(false, true)">
                没译好
              </UiButton>
            </div>
          </template>
        </template>

        <template v-else-if="isFill">
          <FillAnswer
            v-model:user-input="userInput"
            :current="current"
            :judge-result="judgeResult"
            :judging="judging"
            :submitting="submitting"
            :review-saved="reviewSaved"
            @submit="submitFill"
            @next="nextFill"
            @mark="(result) => submitReview(result, true)"
          />
        </template>

        <template v-else-if="isSolution">
          <SolutionAnswer
            v-model:user-input="userInput"
            :current="current"
            :grade-result="gradeResult"
            :grading="grading"
            :submitting="submitting"
            :review-saved="reviewSaved"
            @grade="submitSolution"
            @mark="(result) => submitReview(result, true)"
            @save-result="(result) => submitReview(result, true)"
          />
        </template>

        <template v-else>
          <p class="muted hint">先在心里作答，再点击按钮查看参考答案。</p>
          <div v-if="revealed" class="answer-block">
            <div class="block-label">参考答案</div>
            <MathText :text="current.correct_answer || '暂无参考答案'" />
          </div>
          <div v-if="revealed && current.analysis" class="analysis-block">
            <div class="block-label">解析</div>
            <MathText :text="current.analysis" />
          </div>
          <div class="review-footer">
            <UiButton
              v-if="!revealed"
              variant="primary"
              size="lg"
              @click="revealed = true"
            >
              显示参考答案
            </UiButton>
            <template v-else>
              <UiButton variant="success" size="lg" :loading="submitting" @click="submitReview(true)">
                记住了
              </UiButton>
              <UiButton variant="outline" size="lg" :loading="submitting" @click="submitReview(false)">
                没记住
              </UiButton>
            </template>
          </div>
        </template>

        <div class="kbd-hints">
          <template v-if="isMock"><span><kbd>1-4</kbd> 作答</span><span><kbd>↵</kbd> 下一题 / 末题交卷</span></template>
          <template v-else-if="isMulti && !answered"><span><kbd>1-4</kbd> 勾选/取消</span><span><kbd>↵</kbd> 提交</span></template>
          <template v-else-if="isChoice && !answered"><span><kbd>1-4</kbd>/<kbd>A-D</kbd> 选选项</span><span><kbd>↵</kbd> 确认</span></template>
          <template v-else-if="isChoice && reviewSaved"><span><kbd>↵</kbd> 下一题</span></template>
          <template v-else-if="isTranslation && judgeResult"><span><kbd>↵</kbd>/<kbd>Q</kbd> 译对了</span><span><kbd>W</kbd> 没译好</span></template>
          <template v-else-if="isTranslation"><span><kbd>Ctrl+↵</kbd> 提交译文</span></template>
          <template v-else-if="isFill && judgeResult"><span><kbd>↵</kbd> 下一题</span><span><kbd>Q</kbd>/<kbd>W</kbd> 记住/没记住</span></template>
          <template v-else-if="isSolution && gradeResult"><span><kbd>↵</kbd> 按分数保存</span></template>
          <template v-else-if="!isChoice && !isFill && !isSolution && !isTranslation"><span><kbd>空格</kbd> 显示答案</span><span><kbd>Q</kbd>/<kbd>W</kbd> 记住/没记住</span></template>
          <template v-else-if="isFill || isSolution"><span><kbd>Ctrl+↵</kbd> 提交作答</span></template>
        </div>
      </GlassCard>
      </div>
    </template>

    <UiEmpty v-else-if="!loading" :text="emptyText" icon="check" />
    <GlassCard v-else class="stage-card" :hover="false">
      <div style="display: flex; flex-direction: column; gap: 14px">
        <Skeleton variant="text" :width="'35%'" />
        <Skeleton variant="rect" :height="120" :radius="14" />
        <Skeleton variant="rect" :height="44" :width="'40%'" :radius="12" />
      </div>
    </GlassCard>
  </div>
</template>

<style scoped>
.remaining { align-self: center; }

/* ---------- 沉浸舞台 ---------- */
.stage-wrap {
  position: relative;
  max-width: 860px;
  margin: 0 auto;
}
/* 巨型汉字数字：戏台纵深 */
.stage-numeral {
  position: absolute;
  top: -84px;
  right: -14px;
  z-index: 0;
  font-size: 230px;
  font-weight: 900;
  line-height: 1;
  color: var(--ink);
  opacity: 0.055;
  pointer-events: none;
  user-select: none;
  animation: numeral-in 0.65s var(--ease) both;
}
@keyframes numeral-in {
  from { opacity: 0; transform: translateY(26px) rotate(5deg) scale(0.9); }
  to { opacity: 0.055; transform: translateY(0) rotate(0deg) scale(1); }
}

.top-progress {
  position: relative;
  z-index: 1;
  height: 4px;
  max-width: 860px;
  margin: 0 auto 24px;
  border-radius: 99px;
  background: var(--surface-2);
  overflow: hidden;
}
.tp-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent), #d0664c, #d0664c, var(--accent));
  background-size: 200% 100%;
  animation: tp-flow 3s linear infinite;
  transition: width 0.7s var(--spring);
}
@keyframes tp-flow { to { background-position: 200% 0; } }

.stage-card { position: relative; z-index: 1; max-width: 860px; margin: 0 auto; }

.hint { margin: 10px 0; }

.review-passage {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
}
.review-passage .block-label { margin-bottom: 6px; }
.rp-text { white-space: pre-wrap; line-height: 1.9; font-size: 14px; color: var(--ink); }
.rp-trans { margin-top: 10px; }
.rp-trans summary { cursor: pointer; font-size: 12.5px; font-weight: 700; color: var(--teal); }
.rp-trans-text { margin-top: 6px; white-space: pre-wrap; line-height: 1.8; font-size: 12.5px; color: var(--ink-2); }

.kbd-hints {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 16px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  font-size: 11px;
  color: var(--ink-3);
}
.kbd-hints kbd {
  display: inline-block;
  min-width: 18px;
  padding: 1px 5px;
  margin-right: 2px;
  text-align: center;
  border: 1px solid var(--line);
  border-bottom-width: 2px;
  border-radius: 5px;
  background: var(--surface-2);
  font-size: 10px;
  font-family: var(--font-body);
}

.done-stage {
  max-width: 520px;
  margin: 48px auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 52px 32px 40px;
  text-align: center;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-xl);
  animation: done-in 0.5s var(--spring) both;
}
@keyframes done-in {
  from { opacity: 0; transform: translateY(22px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
/* 落章：从空中盖章 + 回弹 */
.stamp {
  width: 108px;
  height: 108px;
  display: grid;
  place-items: center;
  border-radius: 22px;
  background: var(--accent-grad);
  color: #fff;
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 32px;
  line-height: 1.25;
  box-shadow: 0 10px 28px rgba(168, 51, 32, 0.4), inset 0 2px 0 rgba(255, 255, 255, 0.25);
  animation: stamp-in 0.6s var(--spring) both, stamp-thud 0.3s var(--ease) 0.38s;
  margin-bottom: 8px;
}
@keyframes stamp-in {
  0% { transform: rotate(-6deg) scale(2.4); opacity: 0; }
  60% { transform: rotate(-6deg) scale(0.94); opacity: 1; }
  100% { transform: rotate(-6deg) scale(1); }
}
@keyframes stamp-thud {
  0% { transform: rotate(-6deg) scale(1); }
  40% { transform: rotate(-7deg) scale(1.05); }
  100% { transform: rotate(-6deg) scale(1); }
}
.done-title { font-family: var(--font-display); font-size: 26px; font-weight: 900; margin: 0; }
.done-sub { color: var(--ink-2); margin: 0; }
.done-sub .ok { color: var(--green); }
.done-sub .bad { color: var(--red); }
.done-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 10px; }

/* ---------- 真题模考 ---------- */
.mock-timer {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--gold-soft);
  color: var(--gold);
  font-size: 14px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}
.mock-timer.danger {
  background: var(--red-soft);
  color: var(--red);
  animation: timer-blink 1s var(--ease) infinite;
}
@keyframes timer-blink {
  50% { opacity: 0.55; }
}
.mock-note {
  margin: 0 0 12px;
  font-size: 12.5px;
  color: var(--gold);
}
.mock-report { padding-bottom: 26px; }
.mr-body {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
  flex-wrap: wrap;
  padding: 8px 0 6px;
}
.mr-stats { display: flex; flex-direction: column; gap: 10px; min-width: 220px; }
.mr-line { display: flex; align-items: baseline; gap: 10px; font-size: 13.5px; color: var(--ink-2); }
.mr-line b { font-family: var(--font-display); font-size: 17px; font-weight: 900; color: var(--ink); }
.mr-line span { width: 42px; flex: none; font-size: 12px; color: var(--ink-3); }
.mr-ok { color: var(--green); }
.mr-bad { color: var(--red); }
.mr-overtime {
  font-style: normal;
  font-size: 11.5px;
  color: var(--red);
  background: var(--red-soft);
  padding: 2px 9px;
  border-radius: 999px;
}
.mr-note {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--ink-3);
}
.mr-wrong { margin-top: 18px; padding-top: 12px; border-top: 1px dashed var(--line); }
.mr-item { padding: 10px 12px; border-radius: var(--r-md); background: var(--surface-2); margin-bottom: 8px; }
.mr-q { margin: 0 0 5px; font-size: 13px; line-height: 1.7; color: var(--ink); }
.mr-ans { margin: 0; font-size: 12.5px; color: var(--ink-2); }
.mr-ans b { font-weight: 800; }
.mr-sep { margin: 0 6px; color: var(--ink-3); }
</style>
