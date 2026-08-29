<script setup>
/** 行内数学文本：$...$ / $$...$$ → KaTeX，其余 HTML 转义并清洗 LaTeX 残留。 */
import { computed } from 'vue'

import 'katex/dist/katex.min.css'
import { escapeHtml, renderMath } from '../utils/markdown'

// 非 $ 段落中的 LaTeX 命令残留兜底（AI 偶尔把 \neq 等裸写在文本里）
const TEXT_CMD_MAP = {
  neq: '≠', geq: '≥', leq: '≤', approx: '≈', equiv: '≡', times: '×', div: '÷',
  pm: '±', mp: '∓', infty: '∞', cdot: '·', rightarrow: '→', leftarrow: '←',
  Rightarrow: '⇒', Leftrightarrow: '⇔', in_: '∈', subset: '⊂', cup: '∪', cap: '∩',
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', theta: 'θ', lambda: 'λ', mu: 'μ',
  xi: 'ξ', pi: 'π', sigma: 'σ', phi: 'φ', varphi: 'φ', omega: 'ω', eta: 'η',
  Delta: 'Δ', Sigma: 'Σ', Omega: 'Ω', Lambda: 'Λ', Phi: 'Φ',
}

function cleanPlainText(value) {
  let text = String(value || '')
  // \neq 这类带反斜杠的命令 → 符号
  text = text.replace(/\\([A-Za-z]+)/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(TEXT_CMD_MAP, name) ? TEXT_CMD_MAP[name] : m,
  )
  // \n 被当换行后残留的孤立 "eq"（如 g(x) 换行 eq 0）→ ≠
  text = text.replace(/(^|\n)(\s*)eq(\s)/g, '$1$2≠$3')
  return text
}

const props = defineProps({
  text: { type: String, default: '' },
})

const html = computed(() => {
  const parts = cleanPlainText(props.text).split(
    /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g,
  )
  return parts
    .map((part) => {
      if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
        return `<span class="math-block">${renderMath(part.slice(2, -2), true)}</span>`
      }
      if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        return renderMath(part.slice(1, -1), false)
      }
      return escapeHtml(part.replace(/\$/g, ''))
    })
    .join('')
})
</script>

<template>
  <span class="math-text" v-html="html"></span>
</template>
