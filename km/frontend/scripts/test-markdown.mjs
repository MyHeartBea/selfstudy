import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { renderMarkdown } from '../src/utils/markdown.js'

const displayMath = renderMarkdown('$$\nx^2 + 1 = 2\n$$')
assert.match(displayMath, /katex-display/)
assert.doesNotMatch(displayMath, /\$\$/)

const table = renderMarkdown('| a | b |\n| --- | --- |\n| 1 | 2 |')
assert.match(table, /<table>/)
assert.match(table, /<th>a<\/th>/)

const heading = renderMarkdown('## 标题')
assert.match(heading, /<h4>标题<\/h4>/)

const code = renderMarkdown('`int x`')
assert.match(code, /<code>int x<\/code>/)

const bold = renderMarkdown('**加粗**')
assert.match(bold, /<strong>加粗<\/strong>/)

const link = renderMarkdown('[示例](https://example.com)')
assert.match(link, /<a href="https:\/\/example\.com"/)

const notePath = fileURLToPath(
  new URL('../../docs/notes/计算机组成原理-定点数编码与类型转换.md', import.meta.url),
)
const noteHtml = renderMarkdown(readFileSync(notePath, 'utf-8'))
assert.doesNotMatch(noteHtml, /\$\$/)
assert.match(noteHtml, /katex-display/)
assert.match(noteHtml, /<table>/)

console.log('markdown render tests passed')
