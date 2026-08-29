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
import { confetti } from '../utils/confetti'
import UiButton from '../ui/UiButton.vue'
import UiEmpty from '../ui/UiEmpty.vue'
import UiProgress from '../ui/UiProgress.vue'
import Icon from '../ui/Icon.vue'

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
  ['curve', 'wrong_time', 'random', 'real_exam'].includes(practiceMode.value),
)
const practiceTitle = computed(
  () =>
    ({
      curve: '记忆曲线练习',
      wrong_time: '按错误时间练习',
      random: '随机抽题',
      real_exam: '真题专项',
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
      res = await request.get('/reviews/practice', { params })
    } else {
      res = await request.get('/reviews/today')
    }
    queue.value = res.data.data || []
    if (!queue.value.length) done.value = !isPractice.value
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
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
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
        <span class="count-tip remaining">待复习 {{ Math.max(0, queue.length - index) }} 题</span>
      </div>
    </div>

    <template v-if="done">
      <div class="done-card card">
        <span class="done-icon"><Icon name="check" :size="30" /></span>
        <h3 class="pop-num">{{ practiceTitle ? '练习完成' : '今日复习完成' }}</h3>
        <p class="done-sub">
          答对 <b class="ok pop-num">{{ resultCount.correct }}</b> 题，答错
          <b class="bad pop-num">{{ resultCount.wrong }}</b> 题
        </p>
        <div class="done-actions">
          <UiButton v-if="isPractice" variant="outline" @click="router.push('/practice')">再练一组</UiButton>
          <UiButton variant="primary" @click="router.push('/mistakes')">返回错题列表</UiButton>
          <UiButton variant="ghost" @click="router.push('/stats')">查看统计</UiButton>
        </div>
      </div>
    </template>

    <template v-else-if="current">
      <UiProgress :percentage="progress" :height="9" class="review-progress" />

      <div class="card card-pad review-card">
        <div class="detail-meta">
          <MistakeMeta :mistake="current" />
          <span v-if="current.days_since_wrong != null" class="count-tip">
            错于 {{ current.days_since_wrong === 0 ? '今天' : current.days_since_wrong + ' 天前' }}
          </span>
          <span v-if="current.days_since_review != null" class="count-tip">
            {{ current.days_since_review === 0 ? '今天复习过' : current.days_since_review + ' 天未复习' }}
          </span>
          <span class="count-tip progress-chip">第 {{ index + 1 }} / {{ queue.length }} 题</span>
        </div>

        <div class="question-block">
          <QuestionImages :images="current.images" />
          <MathText :text="current.question" />
        </div>

        <div v-if="current.difficulty_points" class="difficulty-block">
          <span class="block-label">主要难点</span>
          <MathText :text="current.difficulty_points" />
        </div>

        <template v-if="isChoice">
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
          <template v-if="isMulti && !answered"><span><kbd>1-4</kbd> 勾选/取消</span><span><kbd>↵</kbd> 提交</span></template>
          <template v-else-if="isChoice && !answered"><span><kbd>1-4</kbd>/<kbd>A-D</kbd> 选选项</span><span><kbd>↵</kbd> 确认</span></template>
          <template v-else-if="isChoice && reviewSaved"><span><kbd>↵</kbd> 下一题</span></template>
          <template v-else-if="isTranslation && judgeResult"><span><kbd>↵</kbd>/<kbd>Q</kbd> 译对了</span><span><kbd>W</kbd> 没译好</span></template>
          <template v-else-if="isTranslation"><span><kbd>Ctrl+↵</kbd> 提交译文</span></template>
          <template v-else-if="isFill && judgeResult"><span><kbd>↵</kbd> 下一题</span><span><kbd>Q</kbd>/<kbd>W</kbd> 记住/没记住</span></template>
          <template v-else-if="isSolution && gradeResult"><span><kbd>↵</kbd> 按分数保存</span></template>
          <template v-else-if="!isChoice && !isFill && !isSolution && !isTranslation"><span><kbd>空格</kbd> 显示答案</span><span><kbd>Q</kbd>/<kbd>W</kbd> 记住/没记住</span></template>
          <template v-else-if="isFill || isSolution"><span><kbd>Ctrl+↵</kbd> 提交作答</span></template>
        </div>
      </div>
    </template>

    <UiEmpty v-else-if="!loading" :text="emptyText" icon="check" />
    <div v-else class="card card-pad">
      <div class="skeleton" style="height: 20px; width: 35%; margin-bottom: 12px"></div>
      <div class="skeleton" style="height: 120px; margin-bottom: 12px"></div>
      <div class="skeleton" style="height: 44px; width: 40%"></div>
    </div>
  </div>
</template>

<style scoped>
.remaining { align-self: center; }

.review-progress { margin-bottom: 16px; }

.review-card { max-width: 860px; margin: 0 auto; }
.progress-chip {
  margin-left: auto;
}

.hint { margin: 10px 0; }

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

.done-card {
  max-width: 520px;
  margin: 40px auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 44px 32px;
  text-align: center;
  animation: done-in 0.5s cubic-bezier(0.34, 1.4, 0.64, 1) both;
}
@keyframes done-in {
  from { opacity: 0; transform: translateY(22px) scale(0.94); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.done-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: var(--green-soft);
  color: var(--green);
  margin-bottom: 6px;
  animation: icon-pop 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s both;
}
@keyframes icon-pop {
  from { opacity: 0; transform: scale(0.3) rotate(-20deg); }
  to { opacity: 1; transform: scale(1) rotate(0deg); }
}
.done-card h3 {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
}
.done-sub { color: var(--ink-2); }
.done-sub .ok { color: var(--green); }
.done-sub .bad { color: var(--red); }
.done-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; margin-top: 10px; }
</style>
