import { describe, expect, it } from 'vitest'

import { normalizeLetters, scoreLetters } from '../src/utils/examScoring'

describe('normalizeLetters', () => {
  it('大写化、过滤非法字符并排序', () => {
    expect(normalizeLetters('b a')).toBe('AB')
    expect(normalizeLetters('dbca')).toBe('ABCD')
    expect(normalizeLetters('aef')).toBe('AEF')
    expect(normalizeLetters('gefdcba')).toBe('ABCDEFG')
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

  // 与后端 app/services/answer_service.py::judge_letters 共享的用例表：
  // 落库结果由服务端按同一张表复核，所以这里钉住的正是"两边不许漂移"的那几条。
  it('与后端同口径：重复字母去重、越界字母剔除', () => {
    const CASES = [
      ['aab', 'AB', true],
      ['A A', 'A', true],
      ['abx', 'AB', true],
      ['abd', 'AB', false],
      ['aabc', 'abc', true],
      ['', 'A', false],
      ['ex', 'A', false],
      // 七选五扩展：A-G 同口径（E/F/G 也是合法字母）
      ['e', 'E', true],
      ['gfe', 'EFG', true],
      ['EFG', 'efg', true],
      ['eg', 'EFG', false],
      ['efg', 'EG', false],
    ]
    for (const [user, expected, want] of CASES) {
      expect(scoreLetters(user, expected), `scoreLetters(${user}, ${expected})`).toBe(want)
    }
  })
})
