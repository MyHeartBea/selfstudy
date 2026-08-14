<script setup>
import { computed } from 'vue'

import MathText from './MathText.vue'
import MistakeMeta from './MistakeMeta.vue'
import { formatTime } from '../composables/useBaseData'

const props = defineProps({
  detail: { type: Object, required: true },
})

const optionList = computed(() => {
  if (!props.detail) return []
  return ['A', 'B', 'C', 'D'].map((key) => ({
    key,
    text: props.detail['option_' + key.toLowerCase()],
  }))
})
</script>

<template>
  <div>
    <div class="detail-meta">
      <MistakeMeta :mistake="detail" />
      <el-rate :model-value="detail.difficulty" disabled />
    </div>

    <div class="question-block">
      <MathText :text="detail.question" />
    </div>

    <template v-if="detail.question_type === 'choice'">
      <div
        v-for="opt in optionList"
        :key="opt.key"
        class="option-row"
        :class="{ correct: opt.key === detail.correct_answer }"
      >
        <span class="option-key">{{ opt.key }}</span>
        <MathText :text="opt.text || '（未填写）'" />
        <el-tag v-if="opt.key === detail.correct_answer" type="success" size="small">
          正确答案
        </el-tag>
      </div>
    </template>
    <div v-else class="answer-block">
      <div class="block-label">参考答案</div>
      <MathText :text="detail.correct_answer || '暂无参考答案'" />
      <p
        v-if="detail.answer_aliases && detail.answer_aliases.length"
        class="muted"
        style="margin: 6px 0 0"
      >
        可接受答案：{{ detail.answer_aliases.join('；') }}
      </p>
    </div>

    <div v-if="detail.difficulty_points" class="difficulty-block">
      <div class="block-label">主要难点</div>
      <MathText :text="detail.difficulty_points" />
    </div>

    <div v-if="detail.analysis" class="analysis-block">
      <div class="block-label">解析</div>
      <MathText :text="detail.analysis" />
    </div>

    <div class="info-grid">
      <div><strong>难度：</strong>{{ detail.difficulty }} 星</div>
      <div>
        <strong>解题思路：</strong>
        <MathText v-if="detail.approach" :text="detail.approach" />
        <span v-else>未填写</span>
      </div>
      <div><strong>来源：</strong>{{ detail.source || '未填写' }}</div>
      <div v-if="detail.source_year"><strong>年份：</strong>{{ detail.source_year }}</div>
      <div v-if="detail.source_name"><strong>篇目/卷名：</strong>{{ detail.source_name }}</div>
      <div><strong>创建时间：</strong>{{ formatTime(detail.created_at) }}</div>
    </div>
  </div>
</template>
