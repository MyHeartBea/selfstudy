<!--
  UiEmpty / UiSkeleton —— 空态与加载骨架
  ---------------------------------------------------------------------------
  空态与骨架容易被写成"随便放句话"，但它们决定了两件事：
   1. 空态要**告诉用户下一步做什么**（不只是"暂无数据"）
   2. 骨架的形状要**接近真实内容的形状**，否则加载完会跳版（CLS）

  两者刻意放在同一文件：它们回答的是同一类问题（"这里现在没有内容，但马上会有/需要你动手"），
  而且共享同一套尺寸与间距，分开放容易走形。
-->
<script setup>
defineProps({
  /** empty：空态；skeleton：骨架 */
  variant: { type: String, default: 'empty' },
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
  /** 骨架行数 */
  rows: { type: Number, default: 3 },
  /** 骨架是否带缩略图块 */
  thumb: { type: Boolean, default: false },
})
</script>

<template>
  <div v-if="variant === 'empty'" class="empty">
    <span class="mark" aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3v18M3 12h18" opacity="0.35" />
      </svg>
    </span>
    <p class="t">{{ title || '这里还没有内容' }}</p>
    <p v-if="hint" class="h">{{ hint }}</p>
    <div v-if="$slots.action" class="act"><slot name="action"></slot></div>
  </div>

  <div v-else class="skel" role="status" aria-live="polite" aria-label="正在装载">
    <div v-if="thumb" class="sk-thumb"></div>
    <div class="sk-lines">
      <span
        v-for="i in rows"
        :key="i"
        class="sk-line"
        :style="{ width: i === 1 ? '46%' : i % 2 ? '92%' : '72%' }"
      ></span>
    </div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: clamp(30px, 7vh, 64px) 20px;
  text-align: center;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius);
}
.mark {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: 4px;
  color: var(--ink-3);
  border: 1px solid var(--line);
  border-radius: 50%;
}
.t {
  font-size: var(--fs-h2);
  font-weight: 500;
}
.h {
  color: var(--ink-2);
  font-size: var(--fs-sm);
  max-width: 46ch;
  line-height: 1.7;
}
.act {
  margin-top: 10px;
}

/* 骨架：形状贴合真实卡片（缩略图 + 三行），避免加载完跳版 */
.skel {
  display: flex;
  gap: 16px;
  padding: 18px 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--sky-1);
}
.sk-thumb {
  width: 84px;
  height: 106px;
  flex: none;
  background: var(--sky-2);
  border-radius: var(--radius);
  animation: sk-pulse 1.6s var(--e-settle) infinite;
}
.sk-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 11px;
  justify-content: center;
}
.sk-line {
  height: 11px;
  background: var(--sky-2);
  border-radius: 1px;
  animation: sk-pulse 1.6s var(--e-settle) infinite;
}
.sk-line:nth-child(2) {
  animation-delay: 0.12s;
}
.sk-line:nth-child(3) {
  animation-delay: 0.24s;
}
@keyframes sk-pulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk-thumb,
  .sk-line {
    animation: none;
  }
}
</style>
