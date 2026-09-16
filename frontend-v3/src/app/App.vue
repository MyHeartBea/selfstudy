/** * v3 应用外壳 —— 夜航星图 * * 阶段 0 的职责：把"装置外壳"立起来。 * - 三层背景：WebGL
星点场（最远） / CSS 雾气（中） / 颗粒半调（最近） * - 自定义光标（lerp 跟随；**并存原生光标**，JS
失效不会失去指针） * - 研墨开场启动页（可跳过、真实进度、安全网） * - 内容层由 router-view 接管 * *
之后各阶段只往里加"层"，不改这一层：星点场参数、章节、页面都是替换内容层。 */
<script setup>
import { onMounted, ref } from 'vue'

import InkLoader from './InkLoader.vue'
import Starfield from '../sky/Starfield.vue'
import SkyCursor from '../sky/SkyCursor.vue'

const loading = ref(true)
const bootAt = ref(0)

onMounted(() => {
  bootAt.value = performance.now()
})
</script>

<template>
  <!-- 最远层：WebGL 星点场（星点闪烁 + 按亮度视差） -->
  <Starfield />

  <!-- 中层：CSS 雾气（软边、零 GPU 成本） -->
  <div class="aurora" aria-hidden="true"></div>

  <!-- 近层：材质 -->
  <div class="grain" aria-hidden="true"></div>
  <div class="halftone" aria-hidden="true"></div>

  <!-- 前景：自定义光标 -->
  <SkyCursor />

  <!-- 内容 -->
  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>

  <!-- 启动页：覆盖一切，结束后卸载 -->
  <InkLoader v-if="loading" :min-duration="2100" @done="loading = false" />
</template>
