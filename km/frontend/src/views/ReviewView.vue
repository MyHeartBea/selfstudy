<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import request from '../api/request'
import MathText from '../components/MathText.vue'
import {
  questionTypeColor,
  questionTypeName,
  subjectColor,
  subjectName,
  subSubjectName,
  sourceTypeColor,
  sourceTypeName,
} from '../composables/useBaseData'

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
const optionList = computed(() => {
  if (!current.value) return []
  return ['A', 'B', 'C', 'D'].map((key) => ({
    key,
    text: current.value['option_' + key.toLowerCase()],
  }))
})
const isCorrect = computed(
  () => answered.value && selected.value === current.value?.correct_answer,
)
const gradeVerdictText = computed(() => {
  return {
    correct: '回答正确',
    partial: '部分得分',
    wrong: '回答错误',
  }[gradeResult.value?.verdict] || ''
})

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

function choose(key) {
  if (!answered.value) selected.value = key
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
          <el-tag
            :color="questionTypeColor(current.question_type)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ questionTypeName(current.question_type) }}
          </el-tag>
          <el-tag
            :color="subjectColor(current.subject_id)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ subjectName(current.subject_id) }}
          </el-tag>
          <el-tag v-if="current.sub_subject_id" type="info" effect="plain">
            {{ subSubjectName(current.sub_subject_id) }}
          </el-tag>
          <el-tag
            v-if="current.source_type"
            :color="sourceTypeColor(current.source_type)"
            effect="dark"
            style="color: #fff; border-color: transparent"
          >
            {{ sourceTypeName(current.source_type) }}{{ current.source_year ? ' ' + current.source_year : '' }}
          </el-tag>
          <span v-if="current.days_since_wrong != null" class="count-tip">
            错于 {{ current.days_since_wrong === 0 ? '今天' : current.days_since_wrong + ' 天前' }}
          </span>
          <span v-if="current.days_since_review != null" class="count-tip">
            {{ current.days_since_review === 0 ? '今天复习过' : current.days_since_review + ' 天未复习' }}
          </span>
          <span class="count-tip">第 {{ index + 1 }} / {{ queue.length }} 题</span>
        </div>

        <div class="question-block">
          <MathText :text="current.question" />
        </div>

        <div v-if="current.difficulty_points" class="difficulty-block">
          <span class="difficulty-label">主要难点</span>
          <MathText :text="current.difficulty_points" />
        </div>

        <template v-if="isChoice">
          <div
            v-for="opt in optionList"
            :key="opt.key"
            class="option-row review-option"
            :class="{
              correct: answered && opt.key === current.correct_answer,
              wrong: answered && opt.key === selected && opt.key !== current.correct_answer,
              selected: opt.key === selected,
            }"
            @click="choose(opt.key)"
          >
            <span class="option-key">{{ opt.key }}</span>
            <MathText :text="opt.text || '（未填写）'" />
            <el-tag v-if="answered && opt.key === current.correct_answer" type="success" size="small">
              正确答案
            </el-tag>
            <el-tag v-else-if="answered && opt.key === selected" type="danger" size="small">
              你的选择
            </el-tag>
          </div>

          <div v-if="answered && current.analysis" class="analysis-block">
            <div class="block-label">
              {{ isCorrect ? '回答正确' : '回答错误' }} · 解析
            </div>
            <MathText :text="current.analysis" />
          </div>

          <div v-if="!answered" class="review-footer">
            <el-button
              type="primary"
              size="large"
              :disabled="!selected"
              @click="confirmAnswer"
            >
              确认答案
            </el-button>
          </div>
          <div v-else class="review-footer">
            <el-button
              :type="isCorrect ? 'success' : 'warning'"
              size="large"
              :loading="submitting"
              @click="next"
            >
              {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
            </el-button>
          </div>
        </template>

        <template v-else-if="isFill">
          <template v-if="!judgeResult">
            <el-input
              v-model="userInput"
              type="textarea"
              :rows="3"
              placeholder="输入你的答案，例如 2-ln2"
            />
            <div class="review-footer">
              <el-button
                type="primary"
                size="large"
                :loading="judging"
                @click="submitFill"
              >
                提交答案，自动判断
              </el-button>
            </div>
          </template>
          <template v-else>
            <div
              class="answer-block"
              :style="judgeResult.correct ? '' : 'background:#fdf0f0;border-color:#e87474'"
            >
              <div class="block-label">
                {{ judgeResult.correct ? '回答正确' : '回答错误' }}
              </div>
              <p style="margin: 0">
                参考答案：
                <MathText :text="judgeResult.expected || '暂无'" />
              </p>
              <p v-if="judgeResult.aliases.length" class="muted" style="margin: 6px 0 0">
                可接受答案：{{ judgeResult.aliases.join('；') }}
              </p>
            </div>
            <div v-if="current.analysis" class="analysis-block">
              <div class="block-label">解析</div>
              <MathText :text="current.analysis" />
            </div>
            <div class="review-footer">
              <el-button
                :type="judgeResult.correct ? 'success' : 'warning'"
                size="large"
                :loading="submitting"
                @click="submitReview(judgeResult.correct, true)"
              >
                {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
              </el-button>
            </div>
          </template>
        </template>

        <template v-else-if="isSolution">
          <template v-if="!gradeResult">
            <el-input
              v-model="userInput"
              type="textarea"
              :rows="7"
              placeholder="写下你的完整解答过程，AI 会按步骤批改并给出过程分"
            />
            <div class="review-footer">
              <el-button
                type="primary"
                size="large"
                :loading="grading"
                @click="submitSolution"
              >
                AI 批改我的解答
              </el-button>
              <el-button
                type="success"
                plain
                size="large"
                :disabled="grading"
                :loading="submitting"
                @click="submitReview(true)"
              >
                直接标记：记住了
              </el-button>
              <el-button
                type="warning"
                plain
                size="large"
                :disabled="grading"
                :loading="submitting"
                @click="submitReview(false)"
              >
                直接标记：没记住
              </el-button>
            </div>
          </template>
          <template v-else>
            <div class="grade-card">
              <div class="grade-score">{{ gradeResult.score }}</div>
              <div class="grade-meta">
                <el-tag
                  :type="gradeResult.verdict === 'correct' ? 'success' : (gradeResult.verdict === 'partial' ? 'warning' : 'danger')"
                  effect="dark"
                >
                  {{ gradeVerdictText }}
                </el-tag>
                <span class="grade-tip">满分 100，按过程给分</span>
              </div>
            </div>

            <div v-if="gradeResult.errors.length" class="analysis-block">
              <div class="block-label">错在哪里</div>
              <ul style="margin: 0; padding-left: 18px">
                <li v-for="(item, i) in gradeResult.errors" :key="i">
                  <MathText :text="item" />
                </li>
              </ul>
            </div>

            <div v-if="gradeResult.strengths.length" class="answer-block">
              <div class="block-label">做对的部分</div>
              <ul style="margin: 0; padding-left: 18px">
                <li v-for="(item, i) in gradeResult.strengths" :key="i">
                  <MathText :text="item" />
                </li>
              </ul>
            </div>

            <div v-if="gradeResult.feedback" class="analysis-block">
              <div class="block-label">批改评语</div>
              <MathText :text="gradeResult.feedback" />
            </div>

            <div v-if="gradeResult.solution" class="answer-block">
              <div class="block-label">标准解答（思路 + 推导）</div>
              <MathText :text="gradeResult.solution" />
            </div>

            <div v-if="gradeResult.alternate_methods.length" class="analysis-block">
              <div class="block-label">其他解法</div>
              <ol style="margin: 0; padding-left: 18px">
                <li v-for="(item, i) in gradeResult.alternate_methods" :key="i">
                  <MathText :text="item" />
                </li>
              </ol>
            </div>

            <div class="review-footer">
              <el-button
                type="success"
                size="large"
                :loading="submitting"
                @click="submitReview(gradeResult.score >= 60)"
              >
                {{ gradeResult.score >= 60 ? '记住了，保存并下一题' : '没掌握，保存并下一题' }}
              </el-button>
              <el-button
                type="warning"
                size="large"
                :loading="submitting"
                @click="submitReview(gradeResult.score < 60)"
              >
                {{ gradeResult.score >= 60 ? '其实还没懂，保存为错误' : '其实已经会了，保存为正确' }}
              </el-button>
            </div>
          </template>
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
