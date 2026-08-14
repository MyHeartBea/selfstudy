<script setup>
import { computed } from 'vue'

import MathText from './MathText.vue'

const props = defineProps({
  current: { type: Object, required: true },
  userInput: { type: String, default: '' },
  gradeResult: { type: Object, default: null },
  grading: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  reviewSaved: { type: Boolean, default: false },
})

const emit = defineEmits(['update:userInput', 'grade', 'mark', 'save-result'])

const gradeVerdictText = computed(() => {
  return {
    correct: '回答正确',
    partial: '部分得分',
    wrong: '回答错误',
  }[props.gradeResult?.verdict] || ''
})

const saveCorrect = computed(() => props.gradeResult?.score >= 60)
</script>

<template>
  <div>
    <template v-if="!gradeResult">
      <el-input
        :model-value="userInput"
        type="textarea"
        :rows="7"
        placeholder="写下你的完整解答过程，AI 会按步骤批改并给出过程分"
        @update:model-value="$emit('update:userInput', $event)"
      />
      <div class="review-footer">
        <el-button
          type="primary"
          size="large"
          :loading="grading"
          @click="$emit('grade')"
        >
          AI 批改我的解答
        </el-button>
        <el-button
          type="success"
          plain
          size="large"
          :disabled="grading"
          :loading="submitting"
          @click="$emit('mark', true)"
        >
          直接标记：记住了
        </el-button>
        <el-button
          type="warning"
          plain
          size="large"
          :disabled="grading"
          :loading="submitting"
          @click="$emit('mark', false)"
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
          @click="$emit('save-result', saveCorrect)"
        >
          {{ saveCorrect ? '记住了，保存并下一题' : '没掌握，保存并下一题' }}
        </el-button>
        <el-button
          type="warning"
          size="large"
          :loading="submitting"
          @click="$emit('save-result', !saveCorrect)"
        >
          {{ saveCorrect ? '其实还没懂，保存为错误' : '其实已经会了，保存为正确' }}
        </el-button>
      </div>
    </template>
  </div>
</template>
