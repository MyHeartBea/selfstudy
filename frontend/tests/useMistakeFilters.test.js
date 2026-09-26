import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useMistakeFilters } from '../src/composables/useMistakeFilters'

vi.mock('../src/api/request', () => ({ default: { get: vi.fn() } }))

import request from '../src/api/request'

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

describe('useMistakeFilters.loadMistakes 竞态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('新加载顶掉旧加载：旧请求被 abort，且不算失败、不清新请求的 loading', async () => {
    const calls = []
    request.get.mockImplementation((_url, config) => {
      calls.push(config)
      // 一直挂到被 abort：abort 后以 ERR_CANCELED 拒绝（与 axios 行为一致）
      return new Promise((_resolve, reject) => {
        config.signal.addEventListener('abort', () => {
          const err = new Error('canceled')
          err.code = 'ERR_CANCELED'
          reject(err)
        })
      })
    })
    const { loadMistakes, loading, loadError } = useMistakeFilters()

    const first = loadMistakes()
    await Promise.resolve() // 让第一次请求真的发出去
    loadMistakes() // 第二次加载顶掉第一次
    expect(calls.length).toBe(2)
    expect(calls[0].signal.aborted).toBe(true)

    await first // 旧请求以"被取消"收场：不许置 loadError
    expect(loadError.value).toBe(false)
    expect(loading.value).toBe(true) // loading 归新请求管，不许被旧请求的 finally 关掉
  })
})
