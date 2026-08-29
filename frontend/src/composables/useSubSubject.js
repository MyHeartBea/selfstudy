import { computed } from 'vue'

import { baseData } from './useBaseData'

/**
 * 根据科目 id（ref）派生二级科目选项列表。
 * 原先该 computed 在 KnowledgeEditDialog / MistakeForm / MistakeList /
 * PracticeView / KnowledgeBase 中重复出现 5 次，统一收敛到这里。
 */
export function useSubSubject(subjectIdRef) {
  const subSubjectOptions = computed(() => {
    const subjectId = subjectIdRef.value
    if (!subjectId) return []
    return baseData.subSubjects.filter((item) => item.subject_id === subjectId)
  })

  return { subSubjectOptions }
}
