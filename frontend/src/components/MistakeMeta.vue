<script setup>
/** 错题元信息标签组：题型 / 科目 / 二级科目 / 来源 */
import {
  questionTypeColor,
  questionTypeName,
  sourceTypeColor,
  sourceTypeName,
  subjectColor,
  subjectName,
  subSubjectName,
} from '../composables/useBaseData'
import UiTag from '../ui/UiTag.vue'

defineProps({
  mistake: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <UiTag :color="questionTypeColor(mistake.question_type)" :size="compact ? 'sm' : 'md'">
    {{ questionTypeName(mistake.question_type) }}
  </UiTag>
  <UiTag :color="subjectColor(mistake.subject_id)" :size="compact ? 'sm' : 'md'">
    {{ subjectName(mistake.subject_id) }}
  </UiTag>
  <UiTag v-if="mistake.sub_subject_id" soft :size="compact ? 'sm' : 'md'">
    {{ subSubjectName(mistake.sub_subject_id) }}
  </UiTag>
  <UiTag
    v-if="mistake.source_type"
    :color="sourceTypeColor(mistake.source_type)"
    :size="compact ? 'sm' : 'md'"
  >
    {{ sourceTypeName(mistake.source_type) }}{{ mistake.source_year ? ' ' + mistake.source_year : '' }}
  </UiTag>
</template>
