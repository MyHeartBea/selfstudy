<script setup>
import {
  questionTypeColor,
  questionTypeName,
  subjectColor,
  subjectName,
  subSubjectName,
  sourceTypeColor,
  sourceTypeName,
} from '../composables/useBaseData'

defineProps({
  mistake: { type: Object, required: true },
  /** 卡片等紧凑场景下题型/来源标签使用 small 尺寸 */
  compact: { type: Boolean, default: false },
})
</script>

<template>
  <el-tag
    :color="questionTypeColor(mistake.question_type)"
    effect="dark"
    :size="compact ? 'small' : 'default'"
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
    :size="compact ? 'small' : 'default'"
    style="color: #fff; border-color: transparent"
  >
    {{ sourceTypeName(mistake.source_type) }}{{ mistake.source_year ? ' ' + mistake.source_year : '' }}
  </el-tag>
</template>
