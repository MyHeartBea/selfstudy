/**
 * 「数据备份与回滚」页（整库快照，真的能回滚）。
 *
 * 这一页和其它页面不一样的一点：**它的每一个按钮都会动数据**。所以钉的口径是
 * 1. 展示层纯函数（来源标记翻人话、体积、相对时间）—— "空白来源"会被读成"备份坏了"；
 * 2. 失败态走 `UiLoadError`，不掉进"还没有任何快照"的空态（那会把"没查到"说成"没备份"）；
 * 3. 回滚必须**手输 RESTORE** 才发请求，输错一次都不能发（选错快照 = 整库覆盖）；
 * 4. 请求里的 `confirm` 必须等于快照文件名（服务端那道同名校验是最后一道门）。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get, post } }))

import { ageText, formatKb, labelText, snapshotTiles } from '../src/utils/snapshots.js'
import { confirmState } from '../src/ui/confirm'
import ConfirmHost from '../src/ui/ConfirmHost.vue'
import SnapshotsView from '../src/views/SnapshotsView.vue'

const NOW = new Date(2026, 8, 20, 12, 0, 0) // 2026-09-20 12:00

const ROWS = [
  {
    name: 'kaoyan_mistakes_20260920_090000.db',
    label: '',
    size_kb: 2048,
    created_at: '2026-09-20 09:00:00',
  },
  {
    name: 'kaoyan_mistakes_20260101_080000_before-import-5.db',
    label: 'before-import-5',
    size_kb: 1024,
    created_at: '2026-01-01 08:00:00',
  },
]

const RESTORE_RESULT = {
  name: ROWS[0].name,
  safety_snapshot: 'kaoyan_mistakes_20260920_120000_before-restore.db',
  tables_before: {
    mistakes: 20,
    review_records: 9,
    knowledge_base: 3,
    vocab_items: 0,
    exam_papers: null,
  },
  tables_after: {
    mistakes: 5,
    review_records: 2,
    knowledge_base: 1,
    vocab_items: 0,
    exam_papers: 0,
  },
}

function okEnvelope(data, message = 'success') {
  return { data: { code: 200, data, message } }
}

/** 视图 + 确认弹窗宿主（`confirmDialog` 由 ConfirmHost 渲染，单测里要一起挂）。 */
function mountView() {
  return mount(defineComponent({ render: () => [h(SnapshotsView), h(ConfirmHost)] }), {
    attachTo: document.body,
  })
}

async function flush() {
  for (let i = 0; i < 6; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

function restoreButtons(w) {
  return w.findAll('button').filter((b) => b.text().includes('回滚到这一份'))
}

async function openRestoreDialog(w, index = 0) {
  await restoreButtons(w)[index].trigger('click')
  await flush()
}

/** 弹窗是 Teleport 到 body 的，断言一律查 document（与 uiModal.test.js 同一口径）。 */
function clickDialogButton(label) {
  const btn = Array.from(document.querySelectorAll('button')).find(
    (b) => b.textContent.trim() === label,
  )
  if (!btn) throw new Error(`弹窗里没有文案为「${label}」的按钮`)
  btn.click() // 原生 click：Vue 的 @click 是 addEventListener，trigger 只在 wrapper 上有
}

describe('snapshots 展示层纯函数', () => {
  it('来源标记翻成人话，空标记是"启动自动备份"而不是空白', () => {
    expect(labelText('')).toBe('启动自动备份')
    expect(labelText('manual')).toBe('手动快照')
    expect(labelText('before-import-5')).toBe('导入前（5 条）')
    expect(labelText('before-batch-delete-12')).toBe('批量删除前（12 条）')
    expect(labelText('before-restore')).toBe('回滚前的现场')
    // 认不出的标记原样显示：改成"未知"会把脚本打的名字藏起来，排查时反而没线索
    expect(labelText('before-something-else')).toBe('before-something-else')
  })

  it('formatKb 按量级换单位', () => {
    expect(formatKb(512)).toBe('512 KB')
    expect(formatKb(2048)).toBe('2.0 MB')
    expect(formatKb(3.5 * 1024 * 1024)).toBe('3.50 GB')
    expect(formatKb(undefined)).toBe('0 KB')
  })

  it('ageText：当天说时刻，跨天说相对，脏时间不至于崩', () => {
    expect(ageText('2026-09-20 11:59:00', NOW)).toBe('1 分钟前')
    expect(ageText('2026-09-20 09:00:00', NOW)).toBe('今天 09:00')
    expect(ageText('2026-09-19 09:00:00', NOW)).toBe('昨天 09:00')
    expect(ageText('2026-09-17 09:00:00', NOW)).toBe('3 天前')
    expect(ageText('2026-01-01 08:00:00', NOW)).toBe('2026-01-01')
    expect(ageText('不是时间', NOW)).toBe('时间未知')
    expect(ageText('', NOW)).toBe('时间未知')
  })

  it('瓷砖：一份都没有时也四块齐全，并给出"最早一份"而非空白', () => {
    const tiles = snapshotTiles(ROWS, NOW)
    expect(tiles.map((t) => t.key)).toEqual(['count', 'newest', 'oldest', 'size'])
    expect(tiles[0].value).toBe(2)
    expect(tiles[1].value).toBe('今天 09:00')
    expect(tiles[2].value).toBe('2026-01-01')
    expect(tiles[3].value).toBe('3.0 MB')
    const empty = snapshotTiles([], NOW)
    expect(empty[0].value).toBe(0)
    expect(empty[1].value).toBe('暂无')
    expect(empty[2].value).toBe('暂无')
    expect(snapshotTiles(null, NOW)[0].value).toBe(0)
  })
})

describe('SnapshotsView', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    confirmState.open = false
    confirmState.inputValue = ''
    confirmState.error = ''
    confirmState.input = null
  })

  it('渲染列表：来源翻人话、体积、相对时间，每行一个回滚入口', async () => {
    get.mockResolvedValue(okEnvelope(ROWS))
    const w = mountView()
    await flush()
    expect(get).toHaveBeenCalledWith('/snapshots', { params: { limit: 50 }, silent: true })
    expect(w.text()).toContain('数据备份与回滚')
    expect(restoreButtons(w)).toHaveLength(2)
    const text = w.text()
    expect(text).toContain('启动自动备份')
    expect(text).toContain('导入前（5 条）')
    expect(text).toContain('2.0 MB')
    expect(text).toContain('2026-01-01')
    expect(text).toContain('图片文件不在快照里')
  })

  it('一份快照都没有时是空态，不是错误态', async () => {
    get.mockResolvedValue(okEnvelope([]))
    const w = mountView()
    await flush()
    expect(w.text()).toContain('还没有任何快照')
    expect(w.text()).not.toContain('加载失败')
  })

  it('列表加载失败走失败态并可重试（不许显示成"没备份"）', async () => {
    get.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce(okEnvelope(ROWS))
    const w = mountView()
    await flush()
    expect(w.text()).toContain('快照列表加载失败')
    expect(w.text()).not.toContain('还没有任何快照')
    await w
      .findAll('button')
      .find((b) => b.text().includes('重新加载'))
      .trigger('click')
    await flush()
    expect(get).toHaveBeenCalledTimes(2)
    expect(restoreButtons(w)).toHaveLength(2)
  })

  it('回滚要先手输 RESTORE：小写就拦在弹窗里，一个请求都不发', async () => {
    get.mockResolvedValue(okEnvelope(ROWS))
    const w = mountView()
    await flush()
    await openRestoreDialog(w)
    expect(confirmState.open).toBe(true)
    expect(confirmState.message).toContain('2026-09-20 09:00:00')
    expect(confirmState.message).toContain('图片文件不随快照回滚')

    confirmState.inputValue = 'restore'
    clickDialogButton('确认整库回滚')
    await flush()
    expect(confirmState.open).toBe(true) // 没关掉 = 还没放行
    expect(confirmState.error).toContain('RESTORE')
    expect(post).not.toHaveBeenCalled()

    confirmState.inputValue = 'RESTORE'
    clickDialogButton('确认整库回滚')
    await flush()
    expect(post).toHaveBeenCalledTimes(1)
    expect(post).toHaveBeenCalledWith('/snapshots/restore', {
      name: ROWS[0].name,
      confirm: ROWS[0].name,
    })
  })

  it('回滚成功后把条数对照留在页面上，并重新拉列表', async () => {
    get.mockResolvedValue(okEnvelope(ROWS))
    post.mockResolvedValue(okEnvelope(RESTORE_RESULT, '已回到那份快照'))
    const w = mountView()
    await flush()
    await openRestoreDialog(w)
    confirmState.inputValue = 'RESTORE'
    clickDialogButton('确认整库回滚')
    await flush()
    expect(get).toHaveBeenCalledTimes(2) // 初次 + 回滚后刷新
    const text = w.text()
    expect(text).toContain('刚才回到了')
    expect(text).toContain(RESTORE_RESULT.safety_snapshot)
    expect(text).toContain('20')
    // 缺表要写"无此表"而不是 0：0 条和"这份快照里根本没有这张表"是两件事
    expect(text).toContain('无此表')
  })

  it('服务端拒绝回滚时，原因要留在页面上（不能只飘一条 3 秒 toast）', async () => {
    get.mockResolvedValue(okEnvelope(ROWS))
    post.mockRejectedValue({
      response: {
        data: { message: '回滚前的现场快照失败，已中止（没有反悔点就不能覆盖当前库）' },
      },
    })
    const w = mountView()
    await flush()
    await openRestoreDialog(w)
    confirmState.inputValue = 'RESTORE'
    clickDialogButton('确认整库回滚')
    await flush()
    expect(w.text()).toContain('这次没有做成')
    expect(w.text()).toContain('没有反悔点')
    expect(w.text()).not.toContain('刚才回到了')
  })

  it('「立刻备份一次」打 POST /api/snapshots 并刷新列表', async () => {
    get.mockResolvedValue(okEnvelope(ROWS))
    post.mockResolvedValue(okEnvelope({ name: 'kaoyan_mistakes_20260920_120000_manual.db' }))
    const w = mountView()
    await flush()
    await w
      .findAll('button')
      .find((b) => b.text().includes('立刻备份一次'))
      .trigger('click')
    await flush()
    expect(post).toHaveBeenCalledWith('/snapshots', null, { params: { label: 'manual' } })
    expect(get).toHaveBeenCalledTimes(2)
  })
})
