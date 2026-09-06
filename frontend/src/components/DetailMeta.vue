<script setup>
/** 错题详情正文 v2「卷宗」：小节编辑部标题 + 宋体题干 + 通栏图版 + 选项/答案 + 档案双列 */
import { computed } from 'vue'

import MathText from './MathText.vue'
import RichText from './RichText.vue'
import MistakeMeta from './MistakeMeta.vue'
import QuestionImages from './QuestionImages.vue'
import { formatTime } from '../composables/useBaseData'
import UiStars from '../ui/UiStars.vue'
import UiTag from '../ui/UiTag.vue'

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

const hasOptions = computed(() => optionList.value.some((o) => o.text))
</script>

<template>
  <div class="dossier">
    <header class="dossier-head">
      <MistakeMeta :mistake="detail" />
      <span class="meta-difficulty">
        <UiStars :model-value="detail.difficulty" readonly :size="14" />
      </span>
    </header>

    <!-- 通栏图版 -->
    <div v-if="detail.images && detail.images.length" class="dossier-plates">
      <QuestionImages :images="detail.images" :max-width="640" />
    </div>

    <!-- 题干：宋体大字，直接落在纸面 -->
    <section class="dossier-sec">
      <div class="sec-head">题干</div>
      <div class="dossier-question"><RichText :text="detail.question" /></div>
    </section>

    <!-- 选项 / 参考答案 -->
    <section v-if="hasOptions" class="dossier-sec">
      <div class="sec-head">选项</div>
      <div
        v-for="opt in optionList"
        :key="opt.key"
        class="option-row"
        :class="{ correct: opt.key === detail.correct_answer }"
      >
        <span class="option-key">{{ opt.key }}</span>
        <MathText :text="opt.text || '（未填写）'" />
        <UiTag v-if="opt.key === detail.correct_answer" color="var(--green)" size="sm">正确答案</UiTag>
      </div>
    </section>
    <section v-else class="dossier-sec">
      <div class="sec-head">参考答案</div>
      <div class="verdict-panel">
        <MathText :text="detail.correct_answer || '暂无参考答案'" />
        <p
          v-if="detail.answer_aliases && detail.answer_aliases.length"
          class="muted aliases"
        >
          可接受答案：{{ detail.answer_aliases.join('；') }}
        </p>
      </div>
    </section>

    <!-- 主要难点 -->
    <section v-if="detail.difficulty_points" class="dossier-sec">
      <div class="sec-head">主要难点</div>
      <div class="verdict-panel gold">
        <MathText :text="detail.difficulty_points" />
      </div>
    </section>

    <!-- 解析 -->
    <section v-if="detail.analysis" class="dossier-sec">
      <div class="sec-head">解析</div>
      <div class="dossier-analysis"><RichText :text="detail.analysis" /></div>
    </section>

    <!-- 档案 -->
    <section class="dossier-sec">
      <div class="sec-head">档案</div>
      <dl class="dossier-facts">
        <div class="fact"><dt>解题思路</dt><dd><MathText v-if="detail.approach" :text="detail.approach" /><span v-else class="muted">未填写</span></dd></div>
        <div class="fact"><dt>难度</dt><dd>{{ detail.difficulty }} 星</dd></div>
        <div class="fact"><dt>来源</dt><dd>{{ detail.source || '未填写' }}</dd></div>
        <div v-if="detail.source_year" class="fact"><dt>年份</dt><dd class="num">{{ detail.source_year }}</dd></div>
        <div v-if="detail.source_name" class="fact"><dt>篇目 / 卷名</dt><dd>{{ detail.source_name }}</dd></div>
        <div class="fact"><dt>创建时间</dt><dd class="num">{{ formatTime(detail.created_at) }}</dd></div>
      </dl>
    </section>
  </div>
</template>

<style scoped>
/* 卷宗阅读宽度：xl 弹窗下约束行长 */
.dossier {
  max-width: 960px;
  margin: 0 auto;
}
.dossier-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.meta-difficulty { display: inline-flex; margin-left: auto; }

/* 通栏图版 */
.dossier-plates :deep(.question-images) {
  margin: 4px 0 0;
  gap: 12px;
}
.dossier-plates :deep(.question-image) {
  padding: 6px;
  border-radius: 10px;
  background: #fffdf9;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-1);
}
.dossier-plates :deep(img) { border-radius: 4px; }

/* 小节编辑部标题 */
.dossier-sec { margin-top: 20px; }
.sec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
  font-weight: 800;
  letter-spacing: 0.16em;
  color: var(--ink-3);
  margin-bottom: 10px;
}
.sec-head::before {
  content: '';
  width: 16px;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.75;
}

/* 题干：宋体大字 */
.dossier-question {
  font-size: 16px;
  line-height: 1.95;
  color: var(--ink);
}

/* 语义面板（答案/难点） */
.verdict-panel {
  padding: 13px 16px;
  border-radius: var(--r-md);
  background: var(--green-soft);
  border-left: 3px solid color-mix(in srgb, var(--green) 65%, transparent);
  line-height: 1.85;
}
.verdict-panel.gold {
  background: var(--gold-soft);
  border-left-color: color-mix(in srgb, var(--gold) 65%, transparent);
}
.aliases { margin: 6px 0 0; }

/* 解析：平铺阅读区 */
.dossier-analysis {
  font-size: 14px;
  line-height: 1.92;
  color: var(--ink);
}

/* 档案双列 */
.dossier-facts {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 28px;
  padding: 14px 16px;
  border: 1px dashed var(--line-strong);
  border-radius: var(--r-md);
}
.fact { min-width: 0; }
.fact dt {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--ink-3);
  margin-bottom: 3px;
}
.fact dd {
  margin: 0;
  font-size: 13.5px;
  color: var(--ink);
  line-height: 1.75;
}
@media (max-width: 720px) {
  .dossier-facts { grid-template-columns: 1fr; }
}
</style>
