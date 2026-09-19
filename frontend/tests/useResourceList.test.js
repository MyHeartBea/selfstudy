/** useResourceList：列表加载外壳的状态机（成功 / 失败 / 重试 / 两种信封） */
import { describe, expect, it, vi } from 'vitest'

import { useResourceList } from '../src/composables/useResourceList'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('useResourceList', () => {
  it('分页信封：items 与 total 各归其位', async () => {
    const { items, total, loading, loadError, load } = useResourceList(async () => ({
      items: [{ id: 1 }, { id: 2 }],
      total: 83,
    }))
    await load()
    expect(items.value).toHaveLength(2)
    expect(total.value).toBe(83)
    expect(loading.value).toBe(false)
    expect(loadError.value).toBe(false)
  })

  it('全量数组信封：total 回退为数组长度', async () => {
    const { items, total, load } = useResourceList(async () => [{ id: 1 }])
    await load()
    expect(items.value).toHaveLength(1)
    expect(total.value).toBe(1)
  })

  it('data 为 null（后端空响应）不等于失败', async () => {
    const { items, total, loadError, load } = useResourceList(async () => null)
    await load()
    expect(items.value).toEqual([])
    expect(total.value).toBe(0)
    expect(loadError.value).toBe(false)
  })

  it('请求失败：清空上一次结果并置 loadError（不许掉进空态）', async () => {
    let fail = false
    const { items, total, loadError, load } = useResourceList(async () => {
      if (fail) throw new Error('boom')
      return { items: [{ id: 1 }], total: 1 }
    })
    await load()
    expect(items.value).toHaveLength(1)

    fail = true
    await load()
    expect(items.value).toEqual([])
    expect(total.value).toBe(0)
    expect(loadError.value).toBe(true)
  })

  it('重试成功会把 loadError 清回去', async () => {
    const gate = deferred()
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(gate.promise)
      .mockResolvedValueOnce({ items: [], total: 0 })
    const { loadError, load } = useResourceList(fetcher)

    gate.reject(new Error('offline'))
    await load()
    expect(loadError.value).toBe(true)

    await load()
    expect(loadError.value).toBe(false)
  })

  it('loading 在请求未回时为 true，回来后（含失败）必须落回 false', async () => {
    const gate = deferred()
    const { loading, load } = useResourceList(() => gate.promise)
    const pending = load()
    expect(loading.value).toBe(true)
    gate.reject(new Error('x'))
    await pending
    expect(loading.value).toBe(false)
  })

  it('fetcher 自己同步抛错也被收进失败态', async () => {
    const { loadError, loading, load } = useResourceList(() => {
      throw new Error('bad params')
    })
    await load()
    expect(loadError.value).toBe(true)
    expect(loading.value).toBe(false)
  })
})
