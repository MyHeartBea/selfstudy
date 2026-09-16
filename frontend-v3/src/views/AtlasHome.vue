<!--
  阶段 0 占位首页：只用来验证"外壳可跑 + 启动页动效成立"。
  阶段 3 会把它替换成真正的「观测星表」。
  故意保持极简：本章节不承担最终视觉，只是一块可被替换的内容层。
-->
<script setup>
import { onMounted, ref } from 'vue'

const shown = ref(false)
onMounted(() => {
  // 启动页揭开后再让内容入场，两段动效首尾相接
  requestAnimationFrame(() => {
    shown.value = true
  })
})
</script>

<template>
  <main class="shell home" :class="{ shown }">
    <header class="bar">
      <span class="mono">CORE · KM-02</span>
      <span class="mono">NOCTURNAL ATLAS · v3 骨架</span>
      <span class="mono">PHASE 0</span>
    </header>

    <h1 class="title">
      <span class="ln">未掌握的是暗</span>
      <span class="ln">已掌握的是<em>光</em></span>
    </h1>

    <p class="lead">
      阶段 0 已完成：三层背景（星点场 / 雾气 / 颗粒）、自定义光标、研墨开场启动页、
      设计令牌与基础层。接下来按阶段替换内容层——外壳不再改动。
    </p>

    <dl class="facts">
      <div>
        <dt class="mono">Star points</dt>
        <dd class="num">620</dd>
      </div>
      <div>
        <dt class="mono">Atmos layers</dt>
        <dd class="num">2</dd>
      </div>
      <div>
        <dt class="mono">Cursor</dt>
        <dd class="num">lerp .19</dd>
      </div>
      <div>
        <dt class="mono">Loader</dt>
        <dd class="num">3 段</dd>
      </div>
    </dl>
  </main>
</template>

<style scoped>
.home {
  min-height: 100svh;
  padding: clamp(88px, 13vh, 150px) var(--pad) clamp(40px, 8vh, 90px);
  display: flex;
  flex-direction: column;
  /* 内容入场：错峰上推（启动页揭幕后接管） */
  opacity: 0;
  transform: translateY(18px);
  transition:
    opacity 1s var(--e-settle),
    transform 1.1s var(--e-settle);
}
.home.shown {
  opacity: 1;
  transform: none;
}

.bar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line);
}

.title {
  margin: auto 0;
  padding: clamp(28px, 6vh, 72px) 0;
  font-family: var(--font-han);
  font-weight: 500;
  font-size: var(--fs-giant);
  line-height: 0.86;
  letter-spacing: -0.045em;
  text-transform: uppercase;
}
.title .ln {
  display: block;
  overflow: hidden;
}
.title em {
  font-style: normal;
  color: var(--redshift);
}

.lead {
  max-width: 52ch;
  color: var(--ink-1);
  opacity: 0.9;
}

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1px;
  margin-top: clamp(22px, 4vh, 46px);
  border-top: 1px solid var(--line);
}
.facts > div {
  padding: 16px 16px 16px 0;
  border-right: 1px solid var(--line);
}
.facts > div:last-child {
  border-right: 0;
}
.facts dt {
  margin-bottom: 6px;
}
.facts dd {
  font-family: var(--font-mono);
  font-weight: 300;
  font-size: clamp(1.6rem, 3.4vw, 2.8rem);
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--ink-0);
}
</style>
