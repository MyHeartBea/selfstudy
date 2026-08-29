<script setup>
/** 填空题作答：输入 → 后端自动判分（别名/数值容差）或手动标记 */
import MathText from './MathText.vue'
import UiButton from '../ui/UiButton.vue'

defineProps({
  current: { type: Object, required: true },
  userInput: { type: String, default: '' },
  judgeResult: { type: Object, default: null },
  judging: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  reviewSaved: { type: Boolean, default: false },
})

const emit = defineEmits(['update:userInput', 'submit', 'next', 'mark'])
</script>

<template>
  <div>
    <template v-if="!judgeResult">
      <textarea
        :value="userInput"
        class="field-input"
        rows="3"
        placeholder="输入你的答案，例如 2-ln2"
        @input="$emit('update:userInput', $event.target.value)"
      ></textarea>
      <div class="review-footer">
        <UiButton variant="primary" size="lg" :loading="judging" @click="$emit('submit')">
          提交答案，自动判断
        </UiButton>
        <UiButton variant="success" size="lg" :loading="submitting" :disabled="judging" @click="$emit('mark', true)">
          手动标记：记住了
        </UiButton>
        <UiButton variant="outline" size="lg" :loading="submitting" :disabled="judging" @click="$emit('mark', false)">
          手动标记：没记住
        </UiButton>
      </div>
    </template>
    <template v-else>
      <div class="answer-block" :class="{ wrong: !judgeResult.correct }">
        <div class="block-label">{{ judgeResult.correct ? '回答正确' : '回答错误' }}</div>
        <p style="margin: 0">
          参考答案：<MathText :text="judgeResult.expected || '暂无'" />
        </p>
        <p v-if="judgeResult.aliases?.length" class="muted" style="margin: 6px 0 0">
          可接受答案：{{ judgeResult.aliases.join('；') }}
        </p>
      </div>
      <div v-if="current.analysis" class="analysis-block">
        <div class="block-label">解析</div>
        <MathText :text="current.analysis" />
      </div>
      <div class="review-footer">
        <UiButton
          :variant="judgeResult.correct ? 'success' : 'primary'"
          size="lg"
          :loading="submitting"
          @click="$emit('next')"
        >
          {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
        </UiButton>
      </div>
    </template>
  </div>
</template>
