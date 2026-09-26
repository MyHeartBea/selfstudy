/** 公式挖空：公式段变下划线空位，纯文本保留。 */
import { describe, expect, it } from 'vitest'

import { clozeFormula } from '../src/utils/formulaCloze'

describe('formulaCloze', () => {
  it('掩蔽 \\( \\) 公式段，纯文本保留', () => {
    const out = clozeFormula('设 \\(A^2+2A=O\\) 且秩为 2')
    expect(out).not.toContain('A^2+2A=O')
    expect(out).toContain('设 ')
    expect(out).toContain(' 且秩为 2')
    expect(out).toContain('\\underline')
  })

  it('掩蔽 $$ 块与空串安全', () => {
    expect(clozeFormula('x $$a+b$$ y')).not.toContain('a+b')
    expect(clozeFormula('')).toBe('')
    expect(clozeFormula(null)).toBe('')
    expect(clozeFormula('没有公式的纯文本')).toBe('没有公式的纯文本')
  })

  it('空位长度随原段等比（长公式空位更长）', () => {
    const short = clozeFormula('\\(ab\\)')
    const long = clozeFormula('\\(a+b+c+d+e+f+g+h+i+j+k\\)')
    const units = (s) => (s.match(/\\;/g) || []).length
    expect(units(long)).toBeGreaterThan(units(short))
  })
})
