<script setup>
/**
 * 骑缝徽章（复习舞台题卡右上角的「第 N 题」）：
 * 朱砂渐变胶囊，骑在卡片上缘。防裁切铁律：父容器必须 overflow:visible——
 * 玻璃卡片一律把本组件放进 GlassCard 的 #badge 插槽（外层包裹层），不要放进会裁切的内部。
 */
defineProps({
  text: { type: String, default: '' },
})
</script>

<template>
  <span class="stage-badge">{{ text }}<slot></slot></span>
</template>

<style scoped>
.stage-badge {
  position: absolute;
  top: -15px;
  right: 26px;
  padding: 6px 16px;
  border-radius: 999px;
  background: var(--accent-grad);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
  box-shadow: 0 4px 12px rgba(168, 51, 32, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.22);
  z-index: 5;
}
</style>
