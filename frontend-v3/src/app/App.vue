<!--
  v3 应用外壳 —— 夜航星图
  ---------------------------------------------------------------------------
  职责划分（各阶段只往里加"层"，不改这一层）：
    - 最远层：WebGL 星点场（闪烁 + 视差）
    - 中层：CSS 雾气（软边、零 GPU 成本）
    - 近层：材质（颗粒 / 半调）
    - 前景：自定义光标（并存原生光标，JS 失效不失指针）
    - 内容层：AppShell（导航/滚动叙事）+ router-view
    - 覆盖层：研墨开场启动页（可跳过、真实进度、安全网）
-->
<script setup>
import { ref } from 'vue'

import InkLoader from './InkLoader.vue'
import AppShell from './AppShell.vue'
import Starfield from '../sky/Starfield.vue'
import SkyCursor from '../sky/SkyCursor.vue'

const loading = ref(true)
</script>

<template>
  <!-- 最远层：WebGL 星点场 -->
  <Starfield />

  <!-- 中层：CSS 雾气 -->
  <div class="aurora" aria-hidden="true"></div>

  <!-- 近层：材质 -->
  <div class="grain" aria-hidden="true"></div>
  <div class="halftone" aria-hidden="true"></div>

  <!-- 前景：自定义光标 -->
  <SkyCursor />

  <!-- 导航外壳（滚动隐藏 / 磁吸 / 可访问） -->
  <AppShell />

  <!-- 内容层 -->
  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>

  <!-- 启动页：覆盖一切，结束后卸载 -->
  <InkLoader v-if="loading" :min-duration="2100" @done="loading = false" />
</template>
