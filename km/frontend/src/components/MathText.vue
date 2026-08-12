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

const html = computed(() => {
  const parts = String(props.text || '').split(
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
