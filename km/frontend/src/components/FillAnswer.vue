<script setup>
import MathText from './MathText.vue'

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
      <el-input
        :model-value="userInput"
        type="textarea"
        :rows="3"
        placeholder="输入你的答案，例如 2-ln2"
        @update:model-value="$emit('update:userInput', $event)"
      />
      <div class="review-footer">
        <el-button
          type="primary"
          size="large"
          :loading="judging"
          @click="$emit('submit')"
        >
          提交答案，自动判断
        </el-button>
        <el-button
          type="success"
          plain
          size="large"
          :loading="submitting"
          :disabled="judging"
          @click="$emit('mark', true)"
        >
          手动标记：记住了
        </el-button>
        <el-button
          type="warning"
          plain
          size="large"
          :loading="submitting"
          :disabled="judging"
          @click="$emit('mark', false)"
        >
          手动标记：没记住
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
        <p v-if="judgeResult.aliases?.length" class="muted" style="margin: 6px 0 0">
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
          @click="$emit('next')"
        >
          {{ reviewSaved ? '已保存，下一题' : '保存并下一题' }}
        </el-button>
      </div>
    </template>
  </div>
</template>
