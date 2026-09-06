import { describe, expect, it } from 'vitest'

import { normalizeLetters, scoreLetters } from '../src/utils/examScoring'

describe('normalizeLetters', () => {
  it('大写化、过滤非法字符并排序', () => {
    expect(normalizeLetters('b a')).toBe('AB')
    expect(normalizeLetters('dbca')).toBe('ABCD')
    expect(normalizeLetters('aef')).toBe('A')
  })

  it('空值返回空串', () => {
    expect(normalizeLetters('')).toBe('')
    expect(normalizeLetters(null)).toBe('')
  })
})

describe('scoreLetters（单选 + 多选统一判分）', () => {
  it('单选：等值判对', () => {
    expect(scoreLetters('A', 'A')).toBe(true)
    expect(scoreLetters('a', 'A')).toBe(true)
    expect(scoreLetters('A', 'B')).toBe(false)
  })

  it('单选：未作答判错', () => {
    expect(scoreLetters('', 'A')).toBe(false)
    expect(scoreLetters(null, 'A')).toBe(false)
  })

  it('多选：集合相等（顺序无关）判对', () => {
    expect(scoreLetters('ABD', 'ABD')).toBe(true)
    expect(scoreLetters('BAD', 'ABD')).toBe(true)
    expect(scoreLetters('d b a', 'ABD')).toBe(true)
  })

  it('多选：少选/多选均判错', () => {
    expect(scoreLetters('AB', 'ABD')).toBe(false)
    expect(scoreLetters('ABCD', 'ABD')).toBe(false)
    expect(scoreLetters('A', 'AC')).toBe(false)
  })
})
