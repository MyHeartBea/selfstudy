import { computed, reactive, ref } from 'vue'

import request from '../api/request'

/**
 * MistakeList 的筛选 / 分页 / 排序 / 加载逻辑。
 * @param {object} [options]
 * @param {Function} [options.onBeforeLoad] 每次加载列表前回调（用于清空勾选状态）
 */
export function useMistakeFilters({ onBeforeLoad } = {}) {
  const loading = ref(false)
  const loadError = ref(false)
  const items = ref([])
  const total = ref(0)
  const filters = reactive({
    questionType: '',
    subjectId: null,
    subSubjectId: null,
    sourceType: '',
    sourceYear: '',
    difficulties: [],
    tag: '',
    approach: '',
    search: '',
  })
  const sortBy = ref('created_desc')
  const page = ref(1)
  const pageSize = ref(12)

  const activeFilterCount = computed(
    () =>
      [
        filters.questionType,
        filters.subjectId,
        filters.subSubjectId,
        filters.sourceType,
        filters.sourceYear,
        filters.difficulties.length,
        filters.tag,
        filters.approach,
        filters.search,
      ].filter(Boolean).length,
  )

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  /** 由当前筛选条件构建请求参数（不含分页）。 */
  function buildParams() {
    const params = {}
    if (filters.questionType) params.question_type = filters.questionType
    if (filters.subjectId) params.subject_id = filters.subjectId
    if (filters.subSubjectId) params.sub_subject_id = filters.subSubjectId
    if (filters.sourceType) params.source_type = filters.sourceType
    if (filters.sourceYear) params.source_year = filters.sourceYear
    if (filters.difficulties.length) params.difficulty = filters.difficulties
    if (filters.tag) params.tag = filters.tag
    if (filters.approach) params.approach = filters.approach
    if (filters.search) params.search = filters.search
    params.sort = sortBy.value
    return params
  }

  async function loadMistakes() {
    loading.value = true
    loadError.value = false
    if (onBeforeLoad) onBeforeLoad()
    try {
      const params = { ...buildParams(), page: page.value, page_size: pageSize.value }
      const res = await request.get('/mistakes', { params })
      const data = res.data.data || {}
      items.value = data.items || []
      total.value = data.total || 0
      if (data.page) page.value = data.page
    } catch (err) {
      // 错误提示由请求拦截器统一处理；记录错误态供页面区分"真空/加载失败"
      loadError.value = true
    } finally {
      loading.value = false
    }
  }

  function searchMistakes() {
    page.value = 1
    loadMistakes()
  }

  function resetFilters() {
    filters.questionType = ''
    filters.subjectId = null
    filters.subSubjectId = null
    filters.sourceType = ''
    filters.sourceYear = ''
    filters.difficulties = []
    filters.tag = ''
    filters.approach = ''
    filters.search = ''
    searchMistakes()
  }

  function onSubjectChange() {
    filters.subSubjectId = null
    searchMistakes()
  }

  return {
    loading,
    loadError,
    items,
    total,
    filters,
    sortBy,
    page,
    pageSize,
    activeFilterCount,
    totalPages,
    buildParams,
    loadMistakes,
    searchMistakes,
    resetFilters,
    onSubjectChange,
  }
}
