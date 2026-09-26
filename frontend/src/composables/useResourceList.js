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
 * 分页（可选）：传第二参 `{ pageSize }` 即接管 page/pageSize（与 UiPagination 的
 * `v-model:page` / `v-model:page-size` 直接对接，`@change="load"` 触发重载）；
 * fetcher 会收到 `{ page, pageSize, signal }`，**必须把 signal 传进请求**。
 * 不传第二参就是原来的"取一次数"用法，fetcher 收到的对象忽略即可。
 *
 * 竞态语义（与 useMistakeFilters 相同）：新 load 顶掉旧 load（abort 旧的）；
 * 被取消的一方不算失败、不清结果、不动新请求的 loading。
 */
import { ref } from 'vue'

/**
 * @param {(ctx: {page: number, pageSize: number, signal: AbortSignal}) => Promise<any>} fetcher
 *   取数函数，返回**已剥壳**的 data（数组或 {items,total}）
 * @param {{pageSize?: number}} [options] 传 pageSize 即接管分页状态
 * @returns {{items: import('vue').Ref<any[]>, total: import('vue').Ref<number>,
 *   loading: import('vue').Ref<boolean>, loadError: import('vue').Ref<boolean>,
 *   page: import('vue').Ref<number>, pageSize: import('vue').Ref<number>,
 *   load: () => Promise<void>}}
 */
export function useResourceList(fetcher, { pageSize: initialPageSize = 20 } = {}) {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const loadError = ref(false)
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  let abort = null

  async function load({ background = false } = {}) {
    if (abort) abort.abort()
    abort = new AbortController()
    const signal = abort.signal
    // background = keep-alive 返回本页时的静默刷新：不挂 loading（骨架屏会把
    // 保留的滚动位置和可见列表冲掉），失败也不清旧数据（旧数据好过空白）
    if (!background) loading.value = true
    loadError.value = false
    try {
      const data = await fetcher({ page: page.value, pageSize: pageSize.value, signal })
      if (Array.isArray(data)) {
        items.value = data
        total.value = data.length
      } else {
        items.value = data?.items || []
        total.value = data?.total || 0
      }
    } catch (err) {
      // 失败时数据有没有根本未知，清空是为了不让上一次的结果假装还在；
      // toast 由 axios 拦截器统一弹，这里只记状态位给 UiLoadError。
      // 主动取消（新 load 顶掉旧的）不是失败：结果归新请求管，别清也别报错。
      if (err?.code !== 'ERR_CANCELED') {
        loadError.value = true
        if (!background) {
          items.value = []
          total.value = 0
        }
      }
    } finally {
      if (!signal.aborted && !background) loading.value = false
    }
  }

  return { items, total, loading, loadError, page, pageSize, load }
}
