<!--
  MathText —— 行内数学渲染（v3）
  ---------------------------------------------------------------------------
  为什么这一页需要它：公式背诵页的内容是 LaTeX，必须真渲染才能核对。
  KaTeX **只在本组件里 import**，而本组件只被 FormulaView 按需加载，
  所以 KaTeX 不会进入任何其它页面的首屏包（见 vite.config.js 的 manualChunks）。

  安全：v-html 注入的是 KaTeX 输出 + 我们自己转义的纯文本。
  KaTeX 默认 `trust: false`（不允许 \href 之类），这里也不开放。
  输入里的 HTML 一律先转义，公式部分交给 KaTeX 解析 —— 不信任 AI 输出的任何标记。

  支持的定界符：$...$ / $$...$$ / \(...\) / \[...\]
  （扫描版 AI 常输出 \(\) 形式，必须一并支持，否则公式会以源码形式裸露在页面上）
-->
<script setup>
import { computed } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps({
  text: { type: String, default: '' },
})

/** 非公式段落里残留的 LaTeX 命令 - 可读符号（AI 偶尔裸写 \neq） */
const CMD = {
  neq: '≠',
  geq: '≥',
  leq: '≤',
  approx: '≈',
  equiv: '≡',
  times: '×',
  div: '÷',
  pm: '±',
  mp: '∓',
  infty: '∞',
  cdot: '·',
  rightarrow: '-',
  leftarrow: '-',
  Rightarrow: '-',
  Leftrightarrow: '-',
  subset: '⊂',
  cup: '∪',
  cap: '∩',
  alpha: 'α',
  beta: 'β',
  gamma: 'γ',
  delta: 'δ',
  theta: 'θ',
  lambda: 'λ',
  mu: 'μ',
  xi: 'ξ',
  pi: 'π',
  sigma: 'σ',
  phi: 'φ',
  omega: 'ω',
  eta: 'η',
  Delta: 'Δ',
  Sigma: 'Σ',
  Omega: 'Ω',
  Lambda: 'Λ',
  Phi: 'Φ',
}

function escapeHtml(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[c],
  )
}

function cleanPlain(value) {
  return String(value || '').replace(/\\([A-Za-z]+)/g, (m, name) =>
    Object.prototype.hasOwnProperty.call(CMD, name) ? CMD[name] : m,
  )
}

function renderMath(body, display) {
  try {
    return katex.renderToString(body, {
      displayMode: !!display,
      throwOnError: false,
      trust: false,
      strict: 'ignore',
      output: 'html',
    })
  } catch {
    // 渲染失败时退化为等宽源码，绝不吞掉内容
    return `<code class="katex-fallback">${escapeHtml(body)}</code>`
  }
}

const html = computed(() => {
  const raw = String(props.text || '')
  if (!raw) return ''
  // 先按四种定界符拆分；**只对非公式部分做命令替换**，否则公式里的 \times 会被改坏
  const parts = raw.split(/(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$[^$\n]+?\$)/g)
  return parts
    .map((part) => {
      const isBlockDollar = part.startsWith('$$') && part.endsWith('$$') && part.length > 4
      const isBlockBracket = part.startsWith('\\[') && part.endsWith('\\]') && part.length > 4
      if (isBlockDollar || isBlockBracket) {
        return `<span class="math-block">${renderMath(part.slice(2, -2), true)}</span>`
      }
      if (part.startsWith('\\(') && part.endsWith('\\)') && part.length > 4) {
        return renderMath(part.slice(2, -2), false)
      }
      if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        return renderMath(part.slice(1, -1), false)
      }
      return escapeHtml(cleanPlain(part).replace(/\$/g, ''))
    })
    .join('')
})
</script>

<template>
  <!-- KaTeX 的输出必须是 HTML，所以这里必须用 v-html。
       安全性由两层保证：非公式段落先 escapeHtml；KaTeX 以 trust:false 运行（不允许 \href 等）。
       所以就地豁免该规则，而不是关掉全项目的 vue/no-v-html。 -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <span class="math-text" v-html="html"></span>
</template>

<style scoped>
.math-text {
  line-height: 1.9;
}
.math-text :deep(.math-block) {
  display: block;
  margin: 8px 0;
  overflow-x: auto;
}
.math-text :deep(.katex) {
  color: inherit;
}
.math-text :deep(.katex-display) {
  margin: 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 0;
}
.math-text :deep(.katex-fallback) {
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--gold);
  padding: 0 2px;
}
</style>
