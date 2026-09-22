import { afterEach, describe, expect, it, vi } from 'vitest'

import { speakEnglish, speechSupported } from '../src/utils/speech'

describe('speech utils', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    delete window.speechSynthesis
    delete window.SpeechSynthesisUtterance
  })

  it('unsupported environment returns false and never throws', () => {
    expect(speechSupported()).toBe(false)
    expect(speakEnglish('hello')).toBe(false)
  })

  it('speaks with cancel-then-enqueue and en-US voice', () => {
    const cancel = vi.fn()
    const speak = vi.fn()
    window.speechSynthesis = { cancel, speak }
    window.SpeechSynthesisUtterance = class {
      constructor(text) {
        this.text = text
      }
    }
    expect(speechSupported()).toBe(true)
    expect(speakEnglish('  abandon  ')).toBe(true)
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(speak).toHaveBeenCalledTimes(1)
    const u = speak.mock.calls[0][0]
    expect(u.text).toBe('abandon')
    expect(u.lang).toBe('en-US')
  })

  it('empty text is a no-op', () => {
    const speak = vi.fn()
    window.speechSynthesis = { cancel: vi.fn(), speak }
    window.SpeechSynthesisUtterance = class {}
    expect(speakEnglish('')).toBe(false)
    expect(speak).not.toHaveBeenCalled()
  })
})
