<script setup>
/** 解答题作答：AI 按步骤批改（分数/错因/得分点/标准解答/其他解法）或手动标记 */
import { computed } from 'vue'

import MathText from './MathText.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'

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
      <textarea
        :value="userInput"
        class="field-input"
        rows="7"
        placeholder="写下你的完整解答过程，AI 会按步骤批改并给出过程分"
        @input="$emit('update:userInput', $event.target.value)"
      ></textarea>
      <div class="review-footer">
        <UiButton variant="primary" size="lg" :loading="grading" @click="$emit('grade')">
          AI 批改我的解答
        </UiButton>
        <UiButton variant="success" size="lg" :disabled="grading" :loading="submitting" @click="$emit('mark', true)">
          直接标记：记住了
        </UiButton>
        <UiButton variant="outline" size="lg" :disabled="grading" :loading="submitting" @click="$emit('mark', false)">
          直接标记：没记住
        </UiButton>
      </div>
    </template>
    <template v-else>
      <div class="grade-card">
        <div class="grade-score" :class="gradeResult.verdict">{{ gradeResult.score }}</div>
        <div class="grade-meta">
          <UiTag
            :color="gradeResult.verdict === 'correct' ? 'var(--green)' : (gradeResult.verdict === 'partial' ? 'var(--gold)' : 'var(--red)')"
          >
            {{ gradeVerdictText }}
          </UiTag>
          <span class="grade-tip">满分 100，按过程给分</span>
        </div>
      </div>

      <div v-if="gradeResult.errors && gradeResult.errors.length" class="answer-block wrong">
        <div class="block-label">错在哪里</div>
        <ul class="grade-list">
          <li v-for="(item, i) in gradeResult.errors" :key="i"><MathText :text="item" /></li>
        </ul>
      </div>

      <div v-if="gradeResult.strengths && gradeResult.strengths.length" class="answer-block">
        <div class="block-label">做对的部分</div>
        <ul class="grade-list">
          <li v-for="(item, i) in gradeResult.strengths" :key="i"><MathText :text="item" /></li>
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

      <div v-if="gradeResult.alternate_methods && gradeResult.alternate_methods.length" class="analysis-block">
        <div class="block-label">其他解法</div>
        <ol class="grade-list">
          <li v-for="(item, i) in gradeResult.alternate_methods" :key="i"><MathText :text="item" /></li>
        </ol>
      </div>

      <div class="review-footer">
        <UiButton variant="success" size="lg" :loading="submitting" @click="$emit('save-result', saveCorrect)">
          {{ saveCorrect ? '记住了，保存并下一题' : '没掌握，保存并下一题' }}
        </UiButton>
        <UiButton variant="outline" size="lg" :loading="submitting" @click="$emit('save-result', !saveCorrect)">
          {{ saveCorrect ? '其实还没懂，保存为错误' : '其实已经会了，保存为正确' }}
        </UiButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
.grade-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface-2);
  margin: 12px 0;
}
.grade-score {
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 800;
  line-height: 1;
  min-width: 64px;
  text-align: center;
}
.grade-score.correct { color: var(--green); }
.grade-score.partial { color: var(--gold); }
.grade-score.wrong { color: var(--red); }
.grade-meta { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }
.grade-tip { font-size: 12px; color: var(--ink-3); }
.grade-list { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
</style>
