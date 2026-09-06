import { describe, expect, it } from 'vitest'

import { useMistakeFilters } from '../src/composables/useMistakeFilters'

describe('useMistakeFilters.buildParams', () => {
  it('空筛选时只带排序', () => {
    const { buildParams } = useMistakeFilters()
    expect(buildParams()).toEqual({ sort: 'created_desc' })
  })

  it('各筛选字段映射到后端参数名', () => {
    const { buildParams, filters, sortBy } = useMistakeFilters()
    filters.questionType = 'choice'
    filters.subjectId = 2
    filters.sourceType = 'real_exam'
    filters.sourceYear = '2021'
    filters.difficulties = [3, 4]
    filters.tag = ' 二叉树 '
    filters.search = 'arp'
    sortBy.value = 'difficulty_desc'

    expect(buildParams()).toEqual({
      question_type: 'choice',
      subject_id: 2,
      source_type: 'real_exam',
      source_year: '2021',
      difficulty: [3, 4],
      tag: ' 二叉树 ',
      search: 'arp',
      sort: 'difficulty_desc',
    })
  })

  it('activeFilterCount 统计非空筛选数量', () => {
    const { activeFilterCount, filters } = useMistakeFilters()
    expect(activeFilterCount.value).toBe(0)
    filters.questionType = 'fill'
    filters.subjectId = 1
    expect(activeFilterCount.value).toBe(2)
  })

  it('totalPages 至少为 1', () => {
    const { totalPages, total } = useMistakeFilters()
    total.value = 0
    expect(totalPages.value).toBe(1)
    total.value = 13
    expect(totalPages.value).toBe(3) // pageSize 默认 6
  })
})
