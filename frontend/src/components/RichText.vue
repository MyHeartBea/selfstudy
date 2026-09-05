<script setup>
/** Markdown + KaTeX 富文本渲染 */
import { computed } from 'vue'

import 'katex/dist/katex.min.css'
import { renderMarkdown } from '../utils/markdown'

const props = defineProps({
  text: { type: String, default: '' },
})

const html = computed(() => renderMarkdown(props.text))
</script>

<template>
  <div class="rich-text" v-html="html"></div>
</template>

<style scoped>
.rich-text :deep(.hex-dump) {
  font-family: ui-monospace, 'Consolas', 'Menlo', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
  overflow-x: auto;
  margin: 8px 0;
  padding: 10px 12px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--ink);
}
</style>
