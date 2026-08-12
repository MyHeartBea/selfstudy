<script setup>
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
