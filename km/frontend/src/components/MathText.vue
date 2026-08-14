<script setup>
import { computed } from 'vue'

import 'katex/dist/katex.min.css'
import { escapeHtml, renderMath } from '../utils/markdown'

const props = defineProps({
  text: { type: String, default: '' },
})

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
