<script setup>
import {
  formatTime,
  questionTypeColor,
  questionTypeName,
  subjectColor,
  subjectName,
  subSubjectName,
  sourceTypeColor,
  sourceTypeName,
} from '../composables/useBaseData'
import MathText from './MathText.vue'

defineProps({
  mistake: { type: Object, required: true },
})

defineEmits(['open'])
</script>

<template>
  <el-card shadow="hover" class="mistake-card" @click="$emit('open', mistake.id)">
    <div class="card-top">
      <el-tag
        :color="questionTypeColor(mistake.question_type)"
        effect="dark"
        size="small"
        style="color: #fff; border-color: transparent"
      >
        {{ questionTypeName(mistake.question_type) }}
      </el-tag>
      <el-tag
        :color="subjectColor(mistake.subject_id)"
        effect="dark"
        style="color: #fff; border-color: transparent"
      >
        {{ subjectName(mistake.subject_id) }}
      </el-tag>
      <el-tag v-if="mistake.sub_subject_id" type="info" effect="plain">
        {{ subSubjectName(mistake.sub_subject_id) }}
      </el-tag>
      <el-tag
        v-if="mistake.source_type"
        :color="sourceTypeColor(mistake.source_type)"
        effect="dark"
        size="small"
        style="color: #fff; border-color: transparent"
      >
        {{ sourceTypeName(mistake.source_type) }}{{ mistake.source_year ? ' ' + mistake.source_year : '' }}
      </el-tag>
      <el-rate
        :model-value="mistake.difficulty"
        disabled
        size="small"
        class="card-rate"
      />
    </div>
    <div class="question-text">
      <MathText :text="mistake.question" />
    </div>
    <div class="tag-row">
      <el-tag v-for="t in mistake.knowledge_tags" :key="t" size="small" class="tag-item">
        {{ t }}
      </el-tag>
    </div>
    <div class="card-foot">
      <el-tag
        v-if="mistake.review_paused"
        size="small"
        type="info"
        effect="plain"
      >
        已暂停
      </el-tag>
      <span v-else-if="mistake.next_review_at" class="source">
        下次 {{ formatTime(mistake.next_review_at).slice(5) }}
      </span>
      <span v-if="mistake.source_name" class="source">{{ mistake.source_name }}</span>
      <span v-if="mistake.source" class="source">{{ mistake.source }}</span>
      <span v-else class="source"></span>
      <span>{{ formatTime(mistake.created_at) }}</span>
    </div>
  </el-card>
</template>
