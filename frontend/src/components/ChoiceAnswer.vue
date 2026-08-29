<script setup>
/** 客观题作答：单选（点选）与多选（勾选，全对才得分）共用。 */
import { computed } from 'vue'

import MathText from './MathText.vue'
import UiButton from '../ui/UiButton.vue'
import UiTag from '../ui/UiTag.vue'

const props = defineProps({
  current: { type: Object, required: true },
  selected: { type: String, default: null }, // 单选字母；多选为排序后的字母串如 "ABD"
  answered: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  reviewSaved: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'confirm', 'next'])

const isMulti = computed(() => props.current?.question_type === 'multi')

const optionList = computed(() => {
  if (!props.current) return []
  return ['A', 'B', 'C', 'D'].map((key) => ({
    key,
    text: props.current['option_' + key.toLowerCase()],
  }))
})

const selectedSet = computed(() => new Set((props.selected || '').split('').filter(Boolean)))

const isCorrect = computed(() => {
  if (!props.answered || !props.current) return false
  if (isMulti.value) {
    const expected = (props.current.correct_answer || '').split('').filter(Boolean).sort().join('')
    return (props.selected || '').split('').filter(Boolean).sort().join('') === expected
  }
  return props.selected === props.current?.correct_answer
})

function choose(key) {
  if (props.answered) return
  if (isMulti.value) {
    const set = new Set(selectedSet.value)
    set.has(key) ? set.delete(key) : set.add(key)
    emit('select', [...set].sort().join(''))
  } else {
    emit('select', key)
  }
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
      class="option-row clickable review-option"
      :class="{
        correct: answered && (isMulti ? selectedSet.has(opt.key) && (current.correct_answer || '').includes(opt.key) : opt.key === current.correct_answer),
        wrong: answered && (isMulti ? selectedSet.has(opt.key) && !(current.correct_answer || '').includes(opt.key) : opt.key === selected && opt.key !== current.correct_answer),
        selected: !answered && (isMulti ? selectedSet.has(opt.key) : opt.key === selected),
      }"
      @click="choose(opt.key)"
    >
      <span class="option-key">
        <svg v-if="isMulti && selectedSet.has(opt.key)" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 12.5 5 5L20 6.5"/></svg>
        <template v-else>{{ opt.key }}</template>
      </span>
      <MathText :text="opt.text || '（未填写）'" />
      <UiTag
        v-if="answered && (current.correct_answer || '').includes(opt.key)"
        color="var(--green)"
        size="sm"
      >
        {{ isMulti ? '正确选项' : '正确答案' }}
      </UiTag>
      <UiTag v-else-if="answered && selectedSet.has(opt.key)" color="var(--red)" size="sm">
        你的选择
      </UiTag>
    </div>

    <p v-if="isMulti && !answered" class="multi-hint">
      多选题：少选、错选、多选均不得分，请勾选所有正确选项
    </p>

    <div v-if="answered && current.analysis" class="analysis-block">
      <div class="block-label">{{ isCorrect ? '回答正确' : '回答错误' }} · 解析</div>
      <MathText :text="current.analysis" />
    </div>

    <div class="review-footer">
      <UiButton v-if="!answered" variant="primary" size="lg" :disabled="!selected" @click="confirmAnswer">
        {{ isMulti ? `提交（已选 ${selected || '0'} 项）` : '确认答案' }}
      </UiButton>
      <UiButton
        v-else
        :variant="isCorrect ? 'success' : 'primary'"
        size="lg"
        :loading="submitting"
        @click="$emit('next')"
      >
        {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
      </UiButton>
    </div>
  </div>
</template>

<style scoped>
.multi-hint {
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--gold);
}
.option-row.selected .option-key {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
</style>
