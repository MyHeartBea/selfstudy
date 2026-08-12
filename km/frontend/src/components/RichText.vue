<script setup>
import { computed } from 'vue'

import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps({
  text: { type: String, default: '' },
})

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderMath(expr, displayMode) {
  try {
    return katex.renderToString(expr, {
      throwOnError: false,
      displayMode,
      strict: false,
    })
  } catch (err) {
    return escapeHtml(expr)
  }
}

function renderInline(text) {
  const parts = String(text).split(
    /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|\*\*[^*]+\*\*)/g,
  )
  return parts
    .map((part) => {
      if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
        return `<span class="math-block">${renderMath(part.slice(2, -2), true)}</span>`
      }
      if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        return renderMath(part.slice(1, -1), false)
      }
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return `<strong>${escapeHtml(part.slice(2, -2))}</strong>`
      }
      return escapeHtml(part)
    })
    .join('')
}

function parseTable(rows) {
  const body = rows
    .map((row) => {
      const line = row.trim()
      if (!line.startsWith('|')) return null
      return line
        .slice(1, -1)
        .split('|')
        .map((cell) => cell.trim())
    })
    .filter(Boolean)
  if (!body.length) return ''
  const hasSeparator =
    body.length > 1 &&
    body[1].every((cell) => /^:?-{2,}:?$/.test(cell.replace(/\s/g, '')))
  const head = hasSeparator ? body[0] : []
  const rowsData = hasSeparator ? body.slice(2) : body
  const thead = head.length
    ? `<thead><tr>${head
        .map((cell) => `<th>${renderInline(cell)}</th>`)
        .join('')}</tr></thead>`
    : ''
  const tbody = `<tbody>${rowsData
    .map(
      (cells) =>
        `<tr>${cells
          .map((cell) => `<td>${renderInline(cell)}</td>`)
          .join('')}</tr>`,
    )
    .join('')}</tbody>`
  return `<table>${thead}${tbody}</table>`
}

function renderBlocks() {
  const lines = String(props.text || '')
    .replace(/\r/g, '')
    .split('\n')
  const html = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index].trim()
    if (!line) {
      index += 1
      continue
    }
    if (line.startsWith('|')) {
      const tableRows = []
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        tableRows.push(lines[index])
        index += 1
      }
      html.push(parseTable(tableRows))
      continue
    }
    if (line.startsWith('## ')) {
      html.push(`<h4>${renderInline(line.slice(3))}</h4>`)
      index += 1
      continue
    }
    if (line.startsWith('> ')) {
      html.push(`<blockquote>${renderInline(line.slice(2))}</blockquote>`)
      index += 1
      continue
    }
    const imageMatch = line.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
    if (imageMatch) {
      html.push(
        `<img src="${escapeHtml(imageMatch[2])}" alt="${escapeHtml(
          imageMatch[1],
        )}" loading="lazy">`,
      )
      index += 1
      continue
    }
    if (/^[-*] /.test(line)) {
      const items = []
      while (index < lines.length && /^[-*] /.test(lines[index].trim())) {
        items.push(`<li>${renderInline(lines[index].trim().slice(2))}</li>`)
        index += 1
      }
      html.push(`<ul>${items.join('')}</ul>`)
      continue
    }
    if (/^\d+\. /.test(line)) {
      const items = []
      while (index < lines.length && /^\d+\. /.test(lines[index].trim())) {
        items.push(`<li>${renderInline(lines[index].trim().replace(/^\d+\. /, ''))}</li>`)
        index += 1
      }
      html.push(`<ol>${items.join('')}</ol>`)
      continue
    }
    html.push(`<p>${renderInline(line)}</p>`)
    index += 1
  }
  return html.join('')
}

const html = computed(() => renderBlocks())
</script>

<template>
  <div class="rich-text" v-html="html"></div>
</template>
