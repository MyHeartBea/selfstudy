/**
 * 命令面板搜索竞态：连打只留最后一发（seq + AbortController 双保险），关面板掐在途请求。
 * mock 掉 request 层：get 返回永不 settle 的 Promise（模拟"一直在途"），
 * 请求被 abort 时 signal.aborted 必须翻 true —— 这是"旧请求真的停了"的证据。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const h = vi.hoisted(() => ({ calls: [] }))

vi.mock('../src/api/request', () => ({
  default: {
    get: vi.fn((_url, config) => {
      h.calls.push(config)
      return new Promise(() => {})
    }),
  },
}))

import { closePalette, onPaletteInput, paletteState } from '../src/ui/commandPalette'

describe('命令面板搜索竞态', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    h.calls.length = 0
    paletteState.searching = false
    paletteState.groups = []
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('连打只留最后一发：旧在途请求被 abort', () => {
    onPaletteInput('极限')
    vi.advanceTimersByTime(220)
    onPaletteInput('极限存在')
    vi.advanceTimersByTime(220)
    expect(h.calls.length).toBe(2)
    expect(h.calls[0].signal.aborted).toBe(true)
    expect(h.calls[1].signal.aborted).toBe(false)
  })

  it('关闭面板掐掉在途搜索', () => {
    onPaletteInput('泰勒')
    vi.advanceTimersByTime(220)
    expect(h.calls.length).toBe(1)
    closePalette()
    expect(paletteState.open).toBe(false)
    expect(h.calls[0].signal.aborted).toBe(true)
  })
})
