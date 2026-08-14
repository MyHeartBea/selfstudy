<script setup>
import { computed } from 'vue'

import MathText from './MathText.vue'

const props = defineProps({
  current: { type: Object, required: true },
  selected: { type: String, default: null },
  answered: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  reviewSaved: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'confirm', 'next'])

const optionList = computed(() => {
  if (!props.current) return []
  return ['A', 'B', 'C', 'D'].map((key) => ({
    key,
    text: props.current['option_' + key.toLowerCase()],
  }))
})

const isCorrect = computed(
  () => props.answered && props.selected === props.current?.correct_answer,
)

function choose(key) {
  if (!props.answered) emit('select', key)
}

function confirmAnswer() {
  if (!props.selected) return
  emit('confirm')
}
</script>

<template>
  <div>
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
        @click="$emit('next')"
      >
        {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
      </el-button>
    </div>
  </div>
</template>
