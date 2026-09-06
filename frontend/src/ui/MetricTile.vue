<script setup>
/**
 * 瓷砖指标卡：色块图标 + 大数字 + 说明。
 * tone = accent | teal | gold | green | violet | blue
 */
import Icon from './Icon.vue'

defineProps({
  icon: { type: String, default: 'chart' },
  value: { type: [String, Number], default: '' },
  unit: { type: String, default: '' },
  label: { type: String, default: '' },
  tone: { type: String, default: 'accent' },
})
</script>

<template>
  <div class="tile">
    <span class="t-icon" :class="`tone-${tone}`"><Icon :name="icon" :size="20" /></span>
    <div class="t-main">
      <div class="t-val num">{{ value }}<span v-if="unit" class="unit">{{ unit }}</span></div>
      <div class="t-label">{{ label }}<slot name="sub"></slot></div>
    </div>
    <span v-if="$slots.spark" class="t-spark"><slot name="spark"></slot></span>
  </div>
</template>

<style scoped>
.tile {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}
.t-icon {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  flex: none;
  display: grid;
  place-items: center;
}
.tone-accent { background: var(--accent-soft); color: var(--accent); }
.tone-teal { background: var(--teal-soft); color: var(--teal); }
.tone-gold { background: var(--gold-soft); color: var(--gold); }
.tone-green { background: var(--green-soft); color: var(--green); }
.tone-violet { background: var(--violet-soft); color: var(--violet); }
.tone-blue { background: var(--blue-soft); color: var(--blue); }

.t-main { min-width: 0; }
.t-val {
  font-family: var(--font-display);
  font-weight: 900;
  font-size: 30px;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.t-val .unit {
  font-size: 13px;
  color: var(--ink-3);
  font-weight: 500;
  margin-left: 2px;
  font-family: var(--font-body);
}
.t-label { font-size: 12.5px; color: var(--ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.t-spark { margin-left: auto; opacity: 0.9; flex: none; }
</style>
