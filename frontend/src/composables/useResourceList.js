/**
 * 列表加载的统一外壳：把「loading / loadError / items / total + 重试」这套
 * 每个列表页都要抄一遍的逻辑收敛成一处。
 *
 * 为什么值得抽出来（都是实际踩过的）：
 * - 「加载失败」和「暂无数据」必须分家：只写 `v-else-if="!items.length"` 会让失败
 *   掉进空态，用户以为库是空的（见 UiLoadError）。
 * - `useMistakeFilters` 早就 return 了 loadError，视图解构时漏掉一个，错误 UI 就
 *   **永远渲染不出来**且三道质量关卡全绿。这里只有一个返回形状，漏不了。
 * - 后端有两种信封（分页 `{items,total}` / 全量数组，见 docs/api.md），
 *   每个页面各写一遍 `data?.items || []` 早晚会写错一个。
 *
 * 只管"取一次数"，不接管分页与筛选状态（那些是页面自己的 URL 同步逻辑）。
 */
import { ref } from 'vue'

/**
 * @param {() => Promise<any>} fetcher 取数函数，返回**已剥壳**的 data（数组或 {items,total}）
 * @returns {{items: import('vue').Ref<any[]>, total: import('vue').Ref<number>,
 *   loading: import('vue').Ref<boolean>, loadError: import('vue').Ref<boolean>,
 *   load: () => Promise<void>}}
 */
export function useResourceList(fetcher) {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const loadError = ref(false)

  async function load() {
    loading.value = true
    loadError.value = false
    try {
      const data = await fetcher()
      if (Array.isArray(data)) {
        items.value = data
        total.value = data.length
      } else {
        items.value = data?.items || []
        total.value = data?.total || 0
      }
    } catch {
      // 失败时数据有没有根本未知，清空是为了不让上一次的结果假装还在；
      // toast 由 axios 拦截器统一弹，这里只记状态位给 UiLoadError。
      items.value = []
      total.value = 0
      loadError.value = true
    } finally {
      loading.value = false
    }
  }

  return { items, total, loading, loadError, load }
}
