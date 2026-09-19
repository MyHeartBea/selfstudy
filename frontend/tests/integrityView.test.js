/**
 * 「数据体检」页（只读巡检）的回归。
 *
 * 钉三件事：
 * 1. 展示层纯函数（体积换算、瓷砖、引用者文案）—— 数字读不对，这页就等于没有；
 * 2. 页面把后端报告**如实**渲染成清单，且**没有任何删除入口**（清理只能在服务器上用脚本显式做）；
 * 3. 失败态走 UiLoadError + 重试，而不是掉进"没有孤儿文件"的空态（那会把"没查到"说成"很干净"）。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('../src/api/request', () => ({ default: { get } }))

import { formatBytes, locatorLabel, summaryTiles } from '../src/utils/integrity.js'
import IntegrityView from '../src/views/IntegrityView.vue'

const REPORT = {
  referenced: 50,
  files: 152,
  bytes_total: 15000000,
  orphans: [
    { rel: 'images/aaa.png', size: 5000, mtime: '2026-08-01', kind: 'image' },
    { rel: 'images/_thumbs/dead.webp', size: 900, mtime: '2026-08-02', kind: 'thumb' },
  ],
  orphan_total: 102,
  orphan_bytes: 1123456,
  orphan_truncated: true,
  protected_recent: 21,
  missing: [{ name: 'gone.png', refs: ['mistakes#12', 'mistakes#13'] }],
  missing_total: 1,
  unparseable_refs: 2,
  keep_days: 1,
  images_dir_exists: true,
}

async function flush() {
  for (let i = 0; i < 4; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

describe('integrity 展示层纯函数', () => {
  it('formatBytes 按量级换单位，非数字不至于 NaN', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(5000)).toBe('5 KB')
    expect(formatBytes(1123456)).toBe('1.1 MB')
    expect(formatBytes(undefined)).toBe('0 B')
  })

  it('为 0 的缺图数照样占位（"0 条"是有价值的结论，不是没数据）', () => {
    const tiles = summaryTiles({ referenced: 3, files: 3, orphan_total: 0, missing_total: 0 })
    expect(tiles.map((t) => t.value)).toEqual([3, 3, 0, 0])
    expect(tiles[3].tone).toBe('green')
    expect(summaryTiles(null)[0].value).toBe(0)
  })

  it('引用者显示成"错题 12 等 2 处"', () => {
    expect(locatorLabel(['mistakes#12', 'mistakes#13'])).toBe('错题 12 等 2 处')
    expect(locatorLabel(['exam_questions#41'])).toBe('真题 41')
    expect(locatorLabel([])).toBe('')
  })
})

describe('IntegrityView', () => {
  beforeEach(() => {
    get.mockReset()
  })

  it('渲染报告数字与两张清单，并截断说明', async () => {
    get.mockResolvedValue({ data: { data: REPORT } })
    const w = mount(IntegrityView)
    await flush()
    expect(get).toHaveBeenCalledWith('/system/integrity', { silent: true })
    expect(w.text()).toContain('数据体检')
    expect(w.text()).toContain('102')
    expect(w.text()).toContain('1.1 MB')
    expect(w.findAll('tbody tr')).toHaveLength(2)
    expect(w.text()).toContain('缩略图') // kind 翻成人话，不露 thumb
    expect(w.text()).toContain('错题 12 等 2 处')
    expect(w.text()).toContain('只列出最大的前 2 个')
    expect(w.text()).toContain('21 个文件在 1 天保护期内')
  })

  it('没有任何删除入口：清理只能在服务器上用脚本显式做', async () => {
    get.mockResolvedValue({ data: { data: REPORT } })
    const w = mount(IntegrityView)
    await flush()
    const labels = w.findAll('button').map((b) => b.text())
    expect(labels.length).toBeGreaterThan(0)
    expect(labels.some((t) => t.includes('删') || t.includes('清理'))).toBe(false)
    expect(w.text()).toContain('--apply')
  })

  it('空报告渲染成"干净"，而不是空白页', async () => {
    get.mockResolvedValue({
      data: {
        data: { ...REPORT, orphans: [], orphan_total: 0, missing: [], missing_total: 0 },
      },
    })
    const w = mount(IntegrityView)
    await flush()
    expect(w.text()).toContain('没有多余的图片文件')
    expect(w.text()).toContain('所有记录的图片都还在')
  })

  it('请求失败走失败态并可重试', async () => {
    get.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce({ data: { data: REPORT } })
    const w = mount(IntegrityView)
    await flush()
    expect(w.text()).toContain('体检数据加载失败')
    expect(w.text()).not.toContain('没有多余的图片文件')
    await w
      .findAll('button')
      .find((b) => b.text().includes('重新加载'))
      .trigger('click')
    await flush()
    expect(w.text()).toContain('102')
    expect(get).toHaveBeenCalledTimes(2)
  })
})
