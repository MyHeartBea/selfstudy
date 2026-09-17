<!--
  RouteVeil —— 站内换页的遮罩转场
  ===========================================================================
  与 BootCalibration 的分工：那个管"首次进入"（整块向上抽走），
  这个管"站内换页"（一道遮罩扫过）。

  实现要点：
    · 遮罩用 transform: scaleY() 而不是 height —— 只影响合成，不触发布局
    · transform-origin 在下沿，扫入时从下往上长；退出时从上沿收走，
      两个方向都由 CSS 过渡驱动，中间靠 Vue 的状态切换
    · 中间加一条极细的折光线（用 v2 的朱砂），让"扫过"有可读的锋面
    · prefers-reduced-motion 时组件根本不出现（由 composable 判定）
-->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})

/** 扫入 / 退出：visible 为真时铺满，为假时收走 */
const state = computed(() => (props.visible ? 'in' : 'out'))
</script>

<template>
  <div class="veil" :class="state" aria-hidden="true">
    <span class="veil__edge"></span>
  </div>
</template>

<style scoped>
.veil {
  position: fixed;
  inset: 0;
  z-index: 9600;
  pointer-events: none;
  background: var(--bg);
  transform: scaleY(0);
  will-change: transform;
  /* 扫入用"快进慢出"（先快速盖住，末尾轻轻停住），退出用更短的时长 */
  transition: transform 0.42s cubic-bezier(0.76, 0, 0.24, 1);
}
/* 扫入：从下沿往上长满 */
.veil.in {
  transform: scaleY(1);
  transform-origin: bottom;
}
/* 退出：从上沿往上收走 —— 与扫入同方向，读起来是"翻过去了" */
.veil.out {
  transform: scaleY(0);
  transform-origin: top;
  transition-duration: 0.34s;
}

/* 锋面折光线：让"扫过"有可读的边界 */
.veil__edge {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0;
}
.veil.in .veil__edge {
  top: 0;
  opacity: 0.9;
}
.veil.out .veil__edge {
  bottom: 0;
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .veil {
    display: none;
  }
}
</style>
