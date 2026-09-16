<!--
  InkCard —— 内容卡片（整块可点）
  ---------------------------------------------------------------------------
  这是 v2 那个真实事故的正面设计：**整块可点必须靠事件绑在卡片本身**，
  不能靠覆盖层（覆盖层会被 z-index 更高的子元素盖住，只剩缝隙能点）。
  所以这里卡片就是一个 <button> 或带 role/tabindex 的容器，内部控件一律 @click.stop。

  交互：
  - 悬停：上浮 + 右侧露出一道"折角"（暗示这张纸是起的）
  - 聚焦：三道同心环（全站统一）
  - 命中：点击卡片任何非控件区域都触发 select
  - 左侧 spine 色条：按科目区分（颜色由调用方传 --spine 变量）
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** 作为按钮渲染（默认真）：整块可点 */
  as: { type: String, default: 'button' },
  /** 是否可交互；false 时渲染为静态 article，内部不放控件 */
  interactive: { type: Boolean, default: true },
  /** 左侧书脊色（CSS 颜色），用于科目区分 */
  spine: { type: String, default: '' },
  /** 是否是"反复错"（加一条左侧红移竖线，与 v2 的标志层语义一致） */
  flagged: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

const tag = computed(() => (props.interactive ? props.as : 'article'))
const style = computed(() => (props.spine ? { '--spine': props.spine } : {}))
</script>

<template>
  <component
    :is="tag"
    class="ink-card"
    :class="{ flagged, flat: !interactive }"
    :style="style"
    :type="interactive && as === 'button' ? 'button' : undefined"
    :role="interactive && as !== 'button' ? 'button' : undefined"
    :tabindex="interactive && as !== 'button' ? 0 : undefined"
    @click="interactive && emit('select')"
    @keydown.enter.prevent="interactive && emit('select')"
    @keydown.space.prevent="interactive && emit('select')"
  >
    <i v-if="spine || flagged" class="spine" aria-hidden="true"></i>
    <slot />
  </component>
</template>

<style scoped>
.ink-card {
  position: relative;
  display: block;
  width: 100%;
  text-align: left;
  padding: 18px 20px 19px;
  background: var(--sky-1);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  color: inherit;
  overflow: hidden;
  transition:
    transform 0.45s var(--e-flare),
    background 0.35s var(--e-settle),
    border-color 0.35s var(--e-settle);
  will-change: transform;
}
.ink-card.flat {
  cursor: default;
}
.ink-card:not(.flat):hover {
  transform: translateY(-3px);
  background: var(--sky-2);
  border-color: var(--line-strong);
}
.ink-card:not(.flat):focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--sky-0),
    0 0 0 4px var(--redshift);
}

/* 折角：右下角一道极淡斜切，只在悬停时出现（纯装饰，不参与命中） */
.ink-card::after {
  content: '';
  position: absolute;
  right: 0;
  bottom: 0;
  width: 18px;
  height: 18px;
  pointer-events: none;
  background: linear-gradient(315deg, var(--sky-3) 0 50%, transparent 50%);
  opacity: 0;
  transition: opacity 0.35s var(--e-settle);
}
.ink-card:not(.flat):hover::after {
  opacity: 1;
}

/* 书脊色条 / 标记层 */
.spine {
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 2px;
  background: var(--spine, var(--ink-3));
}
.flagged .spine {
  background: var(--redshift);
  box-shadow: 0 0 12px oklch(0.665 0.196 34 / 0.5);
}

@media (prefers-reduced-motion: reduce) {
  .ink-card {
    transition: none;
  }
  .ink-card:not(.flat):hover {
    transform: none;
  }
}
</style>
