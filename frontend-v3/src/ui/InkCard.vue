<!--
  InkCard —— 内容卡片（整块可点 + 悬浮式 3D 倾斜）
  ---------------------------------------------------------------------------
  这是 v2 那个真实事故的正面设计：**整块可点必须靠事件绑在卡片本身**，
  不能靠覆盖层（覆盖层会被 z-index 更高的子元素盖住，只剩缝隙能点）。
  所以这里卡片就是一个 <button> 或带 role/tabindex 的容器，内部控件一律 @click.stop。

  悬浮式（tilt）：用户要求"仿照 v2 做成悬浮式"。v2 的手法是
      perspective(900px) + rotateX/rotateY（最大 3°，克制不炫技）+ 跟随指针的高光 sheen。
  这里作为可选能力（`tilt`），因为只有"卡片墙"需要它；
  列表行与静态卡片加倾斜反而会让文字发虚。

  交互：
  - 悬停：上浮 + 折角 +（可选）3D 倾斜与高光跟随指针
  - 聚焦：三道同心环（全站统一）
  - 命中：点击卡片任何非控件区域都触发 select
  - 左侧 spine 色条：按科目区分（颜色由调用方传 --spine 变量）
-->
<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  /** 作为按钮渲染（默认真）：整块可点 */
  as: { type: String, default: 'button' },
  /** 是否可交互；false 时渲染为静态 article，内部不放控件 */
  interactive: { type: Boolean, default: true },
  /** 左侧书脊色（CSS 颜色），用于科目区分 */
  spine: { type: String, default: '' },
  /** 是否是"反复错"（加一条左侧红移竖线，与 v2 的标志层语义一致） */
  flagged: { type: Boolean, default: false },
  /** 悬浮式：指针跟随的 3D 倾斜 + 高光（卡片墙用；列表行不要开） */
  tilt: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

const tag = computed(() => (props.interactive ? props.as : 'article'))
const style = computed(() => (props.spine ? { '--spine': props.spine } : {}))

/** v2 的最大倾斜角：3°，克制不炫技 */
const TILT_MAX = 3
const tiltStyle = ref('')

function onMove(e) {
  if (!props.tilt) return
  // 触屏没有 hover 语义，倾斜会让点击目标漂移
  if (!window.matchMedia('(pointer: fine)').matches) return
  const el = e.currentTarget
  const rect = el.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const px = (e.clientX - rect.left) / rect.width
  const py = (e.clientY - rect.top) / rect.height
  tiltStyle.value = `perspective(900px) rotateX(${((0.5 - py) * TILT_MAX).toFixed(2)}deg) rotateY(${((px - 0.5) * TILT_MAX).toFixed(2)}deg) translateY(-3px)`
  el.style.setProperty('--sheen-x', `${(px * 100).toFixed(1)}%`)
  el.style.setProperty('--sheen-y', `${(py * 100).toFixed(1)}%`)
}

function onLeave(e) {
  if (!props.tilt) return
  tiltStyle.value = ''
  e.currentTarget.style.setProperty('--sheen-x', '50%')
  e.currentTarget.style.setProperty('--sheen-y', '50%')
}
</script>

<template>
  <component
    :is="tag"
    class="ink-card"
    :class="{ flagged, flat: !interactive, tilted: tilt }"
    :style="tilt ? [style, { transform: tiltStyle }] : style"
    :type="interactive && as === 'button' ? 'button' : undefined"
    :role="interactive && as !== 'button' ? 'button' : undefined"
    :tabindex="interactive && as !== 'button' ? 0 : undefined"
    @click="interactive && emit('select')"
    @keydown.enter.prevent="interactive && emit('select')"
    @keydown.space.prevent="interactive && emit('select')"
    @pointermove="onMove"
    @pointerleave="onLeave"
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

/* ── 悬浮式（tilt）────────────────────────────────────────────────
   transform 由 JS 内联样式驱动（perspective + rotateX/rotateY + translateY(-3px)），
   所以这里必须关掉 CSS 的 :hover 位移，否则两者互相覆盖会抖动。 */
.ink-card.tilted {
  transition:
    transform 0.18s linear,
    background 0.35s var(--e-settle),
    border-color 0.35s var(--e-settle);
}
.ink-card.tilted:not(.flat):hover {
  transform: none;
}
/* 跟随指针的高光：位置由 --sheen-x/--sheen-y 控制 */
.ink-card.tilted::before {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0;
  background: radial-gradient(
    360px circle at var(--sheen-x, 50%) var(--sheen-y, 50%),
    oklch(0.945 0.014 265 / 0.1),
    transparent 62%
  );
  transition: opacity 0.3s var(--e-settle);
}
.ink-card.tilted:not(.flat):hover::before {
  opacity: 1;
}
/* 悬浮时的层次：不用大黑阴影（暗底上会脏），用更亮的描边 + 极弱冷光 */
.ink-card.tilted:not(.flat):hover {
  border-color: var(--line-strong);
  box-shadow: 0 18px 40px -26px #000000d9;
}
/* 倾斜时内容不能溢出到相邻卡片上 */
.ink-card.tilted {
  transform-style: preserve-3d;
  will-change: transform;
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
