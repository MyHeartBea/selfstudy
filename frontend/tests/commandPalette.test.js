/**
 * 命令面板 store：全站搜索的摊平 / 分段 / 跳转目标 / 竞态守卫。
 *
 * 钉住三件单测最容易漏的事：
 *  1) 分段渲染后 `activeIndex` 仍是**一维**下标（曾按组内序号走，↑↓ 与鼠标高亮各指一条）；
 *  2) 每种实体的跳转参数名与目标页的筛选参数**同名**（`search`），知识点除外（它按 `tag` 筛）；
 *  3) 慢请求晚返回不能覆盖新结果、失败必须清空（留着上次命中就是假数据）。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const GROUPS = [
  {
    key: 'mistakes',
    label: '错题',
    total: 12,
    items: [{ id: 7, title: '泰勒公式展开', subtitle: '数学二', meta: 'choice' }],
  },
  {
    key: 'knowledge',
    label: '知识点',
    total: 2,
    items: [{ id: 3, title: '泰勒公式', subtitle: '用多项式逼近', meta: '数学二' }],
  },
  {
    key: 'essays',
    label: '作文',
    total: 1,
    items: [{ id: 9, title: 'Write an essay', subtitle: 'goes up', meta: '11/15' }],
  },
]

async function flush(times = 8) {
  for (let i = 0; i < times; i += 1) await Promise.resolve()
}

describe('commandPalette 全站搜索', () => {
  let mod
  let get

  beforeEach(async () => {
    vi.resetModules()
    vi.useFakeTimers()
    get = vi.fn()
    vi.doMock('../src/api/request', () => ({ default: { get } }))
    mod = await import('../src/ui/commandPalette.js')
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function okOnce(groups) {
    return { data: { code: 200, data: { groups } } }
  }

  it('摊平后顺序 = 后端分组顺序，且每组只展示 items（total 不参与长度）', async () => {
    const { paletteState, visibleItems } = mod
    paletteState.query = '泰勒'
    paletteState.groups = GROUPS
    const flat = visibleItems()
    expect(flat.map((r) => [r.kind, r.id])).toEqual([
      ['mistakes', 7],
      ['knowledge', 3],
      ['essays', 9],
    ])
    expect(flat[0].groupLabel).toBe('错题')
  })

  it('scope 只是本地过滤器，不重新打接口', async () => {
    const { paletteState, setScope, visibleItems } = mod
    paletteState.query = '泰勒'
    paletteState.groups = GROUPS
    setScope('essays')
    expect(visibleItems().map((r) => r.kind)).toEqual(['essays'])
    expect(get).not.toHaveBeenCalled()
    // 换过滤器要回到列表首行，否则 activeIndex 会停在已被过滤掉的下标上
    expect(paletteState.activeIndex).toBe(0)
  })

  it('分段里的每行都带一维下标（跨组连续）', async () => {
    const { paletteState, visibleSections } = mod
    paletteState.query = 'x'
    paletteState.scope = 'all'
    paletteState.groups = GROUPS
    const sections = visibleSections()
    expect(sections.map((s) => s.label)).toEqual(['错题', '知识点', '作文'])
    expect(sections.map((s) => s.rows[0].index)).toEqual([0, 1, 2])

    // 同组多条时必须落在同一段里，且下标接着数
    paletteState.groups = [
      {
        ...GROUPS[0],
        items: [
          { id: 1, title: 'a' },
          { id: 2, title: 'b' },
        ],
      },
      GROUPS[1],
    ]
    const two = visibleSections()
    expect(two.map((s) => s.rows.map((r) => r.index))).toEqual([[0, 1], [2]])
  })

  it('跳转目标与目标页的筛选参数同名；知识点按标签回跳', async () => {
    const { paletteState, visibleItems } = mod
    paletteState.query = '泰勒 公式'
    paletteState.groups = GROUPS
    const [mistake, knowledge, essay] = visibleItems()
    expect(mistake.target).toBe('/mistakes?search=' + encodeURIComponent('泰勒 公式'))
    expect(knowledge.target).toBe('/knowledge?tag=' + encodeURIComponent('泰勒公式'))
    expect(essay.target).toBe('/essays?search=' + encodeURIComponent('泰勒 公式'))
  })

  it('打的是 /search?q=，命中组写进 groups', async () => {
    const { paletteState, onPaletteInput } = mod
    get.mockResolvedValue(okOnce(GROUPS))
    onPaletteInput('泰勒')
    expect(paletteState.searching).toBe(true)
    await vi.advanceTimersByTimeAsync(200)
    await flush()
    expect(get).toHaveBeenCalledWith(
      '/search',
      expect.objectContaining({ params: { q: '泰勒' }, silent: true, signal: expect.anything() }),
    )
    expect(paletteState.groups).toHaveLength(3)
    expect(paletteState.searching).toBe(false)
  })

  it('慢的旧请求晚返回，不能覆盖后到的新结果', async () => {
    const { paletteState, onPaletteInput } = mod
    const slow = deferred()
    const fast = deferred()
    get.mockImplementationOnce(() => slow.promise).mockImplementationOnce(() => fast.promise)
    onPaletteInput('旧')
    await vi.advanceTimersByTimeAsync(200)
    onPaletteInput('新')
    await vi.advanceTimersByTimeAsync(200)
    fast.resolve(okOnce([GROUPS[2]]))
    await flush()
    expect(paletteState.groups.map((g) => g.key)).toEqual(['essays'])
    slow.resolve(okOnce(GROUPS))
    await flush()
    expect(paletteState.groups.map((g) => g.key)).toEqual(['essays'])
    // searching 也不能被迟到的 finally 置回 false 之外再乱动
    expect(paletteState.searching).toBe(false)
  })

  it('搜索失败清空结果，而不是留着上一次的命中', async () => {
    const { paletteState, onPaletteInput } = mod
    get.mockResolvedValue(okOnce(GROUPS))
    onPaletteInput('第一次')
    await vi.advanceTimersByTimeAsync(200)
    await flush()
    expect(paletteState.groups).toHaveLength(3)

    get.mockRejectedValueOnce({ response: { status: 500 } })
    onPaletteInput('第二次')
    await vi.advanceTimersByTimeAsync(200)
    await flush()
    expect(paletteState.groups).toEqual([])
    expect(paletteState.searching).toBe(false)
  })

  it('清空输入即清空结果，不发请求', async () => {
    const { paletteState, onPaletteInput } = mod
    paletteState.groups = GROUPS
    onPaletteInput('   ')
    await vi.advanceTimersByTimeAsync(400)
    expect(paletteState.groups).toEqual([])
    expect(get).not.toHaveBeenCalled()
  })
})
