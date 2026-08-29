<script setup>
/** 通用图标组件：<Icon name="search" :size="16" /> */
import { iconSvg } from './icons'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 18 },
})
</script>

<template>
  <span class="icon" style="display: inline-flex; flex: none" v-html="iconSvg(name, Number(size))"></span>
</template>
