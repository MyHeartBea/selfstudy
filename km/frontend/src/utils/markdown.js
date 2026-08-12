import katex from 'katex'

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function renderMath(expr, displayMode) {
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

export function renderInline(text) {
  const parts = String(text).split(
    /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$|\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g,
  )
  return parts
    .map((part) => {
      if (!part) return ''
      if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
        return `<span class="math-block">${renderMath(part.slice(2, -2), true)}</span>`
      }
      if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
        return renderMath(part.slice(1, -1), false)
      }
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return `<strong>${escapeHtml(part.slice(2, -2))}</strong>`
      }
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return `<code>${escapeHtml(part.slice(1, -1))}</code>`
      }
      const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      if (linkMatch) {
        return `<a href="${escapeHtml(linkMatch[2])}" target="_blank" rel="noopener">${escapeHtml(
          linkMatch[1],
        )}</a>`
      }
      return escapeHtml(part.replace(/\$/g, ''))
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
        .replace(/\\\|/g, '\u0000')
        .split('|')
        .map((cell) => cell.replace(/\u0000/g, '\\|').trim())
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

export function renderBlocks(source) {
  const lines = String(source || '').replace(/\r/g, '').split('\n')
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
    if (/^#{1,4}\s+/.test(line)) {
      html.push(`<h4>${renderInline(line.replace(/^#{1,4}\s+/, ''))}</h4>`)
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
        items.push(
          `<li>${renderInline(lines[index].trim().replace(/^\d+\. /, ''))}</li>`,
        )
        index += 1
      }
      html.push(`<ol>${items.join('')}</ol>`)
      continue
    }
    if (/^(-{3,}|\*{3,})$/.test(line)) {
      html.push('<hr>')
      index += 1
      continue
    }
    html.push(`<p>${renderInline(line)}</p>`)
    index += 1
  }
  return html.join('')
}

export function renderMarkdown(text) {
  const source = String(text || '').replace(/\r/g, '')
  const parts = source.split(/(\$\$[\s\S]+?\$\$)/g)
  const html = []
  for (const part of parts) {
    if (!part) continue
    if (part.startsWith('$$') && part.endsWith('$$') && part.length > 4) {
      html.push(
        `<span class="math-block">${renderMath(part.slice(2, -2), true)}</span>`,
      )
    } else {
      html.push(renderBlocks(part))
    }
  }
  return html.join('')
}
