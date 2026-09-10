/**
 * 卡片预览用的 markdownToPlain 回归。
 *
 * 背景：知识点/公式卡片的摘要以前直接截断 Markdown 原文，卡片上会露出
 * `## 核心概念`、`**加粗**`、表格竖线等标记。这里保证标记被剥掉、正文保留。
 */
import { describe, expect, it } from 'vitest'

import { markdownToPlain } from '../src/utils/markdown'

describe('markdownToPlain', () => {
  it('剥掉标题符号（真实数据里最常见的开头）', () => {
    expect(markdownToPlain('## 核心概念\n\n正文内容')).toBe('核心概念 正文内容')
  })

  it('剥掉加粗/斜体标记但保留文字', () => {
    expect(markdownToPlain('**虚拟机（VM）** 是逻辑计算机')).toBe('虚拟机（VM） 是逻辑计算机')
    expect(markdownToPlain('__粗__ 与 *斜*')).toBe('粗 与 斜')
  })

  it('表格不再露出竖线和分隔行', () => {
    const table = [
      '| 对比维度 | 第一类 VMM |',
      '| --- | --- |',
      '| 运行位置 | 直接运行在硬件上 |',
    ].join('\n')
    const out = markdownToPlain(table)
    expect(out).not.toContain('|')
    expect(out).not.toContain('---')
    expect(out).toContain('运行位置')
  })

  it('剥离列表符号、引用符号与代码反引号', () => {
    expect(markdownToPlain('- 要点一\n1. 要点二')).toBe('要点一 要点二')
    expect(markdownToPlain('> ⚠️ 注意')).toBe('⚠️ 注意')
    expect(markdownToPlain('用 `code` 示例')).toBe('用 code 示例')
  })

  it('链接只留文字', () => {
    expect(markdownToPlain('[等价无穷小](http://x.com) 定义')).toBe('等价无穷小 定义')
  })

  it('$$ 公式块被清掉（卡片上不显示源码）', () => {
    const out = markdownToPlain('前言\n\n```\ncode block\n```\n结尾')
    expect(out).not.toContain('code block')
    expect(out).toContain('前言')
  })

  it('空输入安全', () => {
    expect(markdownToPlain('')).toBe('')
    expect(markdownToPlain(null)).toBe('')
    expect(markdownToPlain(undefined)).toBe('')
  })

  it('压缩多余空白成单行', () => {
    expect(markdownToPlain('a\n\n\n  b   c')).toBe('a b c')
  })
})
