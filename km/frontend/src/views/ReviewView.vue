<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import ChoiceAnswer from '../components/ChoiceAnswer.vue'
import FillAnswer from '../components/FillAnswer.vue'
import SolutionAnswer from '../components/SolutionAnswer.vue'
import MathText from '../components/MathText.vue'
import MistakeMeta from '../components/MistakeMeta.vue'
import QuestionImages from '../components/QuestionImages.vue'

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
const isChoice = computed(() => questionType.value === 'choice')
const isFill = computed(() => questionType.value === 'fill')
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
    ElMessage.warning('请输入你的答案')
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
    ElMessage.warning('请写下你的解答过程')
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
      ElMessage.success('复习记录已保存')
      if (result) resultCount.value.correct += 1
      else resultCount.value.wrong += 1
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
    if (index.value >= queue.value.length) done.value = true
  }
}

onMounted(loadQueue)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="view-hero">
      <div class="view-hero-copy">
        <div class="view-kicker">Review Flow</div>
        <h2>{{ practiceTitle || '今日复习' }}</h2>
        <p class="view-desc">按记忆节奏完成复习，只做当前最该做的题。</p>
      </div>
      <div class="header-actions">
        <el-button v-if="isPractice" @click="router.push('/practice')">
          重新选题
        </el-button>
        <span class="count-tip">待复习 {{ queue.length - index }} 题</span>
      </div>
    </div>

    <template v-if="done">
      <el-result
        icon="success"
        :title="practiceTitle ? '练习完成' : '今日复习完成'"
        :sub-title="`答对 ${resultCount.correct} 题，答错 ${resultCount.wrong} 题`"
      >
        <template #extra>
          <el-button @click="router.push('/practice')">
            再练一组
          </el-button>
          <el-button type="primary" @click="router.push('/mistakes')">
            返回错题列表
          </el-button>
          <el-button @click="router.push('/stats')">查看统计</el-button>
        </template>
      </el-result>
    </template>

    <template v-else-if="current">
      <el-progress
        :percentage="progress"
        :stroke-width="10"
        :show-text="false"
        class="review-progress"
      />

      <el-card shadow="never" class="review-card">
        <div class="detail-meta">
          <MistakeMeta :mistake="current" />
          <span v-if="current.days_since_wrong != null" class="count-tip">
            错于 {{ current.days_since_wrong === 0 ? '今天' : current.days_since_wrong + ' 天前' }}
          </span>
          <span v-if="current.days_since_review != null" class="count-tip">
            {{ current.days_since_review === 0 ? '今天复习过' : current.days_since_review + ' 天未复习' }}
          </span>
          <span class="count-tip">第 {{ index + 1 }} / {{ queue.length }} 题</span>
        </div>

        <div class="question-block">
          <QuestionImages :images="current.images" />
          <MathText :text="current.question" />
        </div>

        <div v-if="current.difficulty_points" class="difficulty-block">
          <span class="difficulty-label">主要难点</span>
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
          <p class="muted" style="margin: 10px 0">
            先在心里作答，再点击按钮查看参考答案。
          </p>
          <div v-if="revealed" class="answer-block">
            <div class="block-label">参考答案</div>
            <MathText :text="current.correct_answer || '暂无参考答案'" />
          </div>
          <div v-if="revealed && current.analysis" class="analysis-block">
            <div class="block-label">解析</div>
            <MathText :text="current.analysis" />
          </div>
          <div class="review-footer">
            <el-button
              v-if="!revealed"
              type="primary"
              size="large"
              @click="revealed = true"
            >
              显示参考答案
            </el-button>
            <template v-else>
              <el-button
                type="success"
                size="large"
                :loading="submitting"
                @click="submitReview(true)"
              >
                记住了
              </el-button>
              <el-button
                type="warning"
                size="large"
                :loading="submitting"
                @click="submitReview(false)"
              >
                没记住
              </el-button>
            </template>
          </div>
        </template>
      </el-card>
    </template>

    <el-empty v-else :description="emptyText" />
  </div>
</template>
