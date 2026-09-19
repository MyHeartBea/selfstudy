<script setup>
/**
 * 全局考研倒计时印（外壳层，每个页面都在）。
 * 数据来自 GET /api/exam-countdown（纯日期计算）；日期在 backend/.env 的 EXAM_DATE 配置。
 * 两种形态：桌面 = 右上角悬浮印章；窄屏 = 顶栏紧凑 chip（compact）。
 */
import { computed } from 'vue'

const props = defineProps({
  days: { type: Number, default: null },
  date: { type: String, default: '' },
  passed: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const visible = computed(() => props.days !== null && !props.passed)
// 三档语气：<=7 冲刺（洒金 + 快脉动）、<=30 紧迫（朱砂 + 中脉动）、其余常态
const tier = computed(() => {
  if (props.days === null) return 'calm'
  if (props.days <= 7) return 'final'
  if (props.days <= 30) return 'hot'
  return 'calm'
})
const kicker = computed(() => (tier.value === 'final' ? '最后冲刺' : '距考研'))
const shortDate = computed(() => props.date.slice(5).replace('-', ' · '))
const ariaText = computed(
  () => `距考研 ${props.days} 天${props.date ? `，初试日期 ${props.date}` : ''}`,
)
</script>

<template>
  <span
    v-if="visible"
    class="exam-cd"
    :class="[`tier-${tier}`, { compact }]"
    role="status"
    :aria-label="ariaText"
    :title="ariaText"
  >
    <span class="cd-kicker">{{ kicker }}</span>
    <span class="cd-main">
      <b class="cd-num serif num">{{ days }}</b>
      <span class="cd-unit">天</span>
      <span v-if="!compact && shortDate" class="cd-date num">{{ shortDate }}</span>
    </span>
  </span>
</template>

<style scoped>
.exam-cd {
  position: fixed;
  top: 14px;
  /* 与正文右边缘对齐；视口窄到装不下时退回贴边 16px */
  right: max(16px, calc(50vw - (var(--content-max) / 2) + 6px));
  z-index: 918;
  display: grid;
  gap: 2px;
  align-content: center;
  min-width: 152px;
  padding: 10px 16px;
  border-radius: 16px;
  background:
    linear-gradient(
        color-mix(in srgb, var(--accent) 7%, var(--surface-glass)),
        color-mix(in srgb, var(--accent) 3%, var(--surface-glass))
      )
      padding-box,
    linear-gradient(
        135deg,
        color-mix(in srgb, var(--accent) 62%, transparent),
        transparent 40%,
        color-mix(in srgb, var(--gold) 52%, transparent) 78%,
        color-mix(in srgb, var(--accent) 38%, transparent)
      )
      border-box;
  border: 1px solid transparent;
  backdrop-filter: blur(18px) saturate(1.3);
  box-shadow: var(--shadow-2);
  overflow: hidden;
  opacity: 0;
  transform: translateY(-10px) scale(0.96);
  transition:
    opacity var(--dur-4) var(--ease-enter),
    transform var(--dur-4) var(--ease-spring);
}
:global(body.app-ready .exam-cd) {
  opacity: 1;
  transform: none;
}
/* 掠过的洒金反光（一次性扫过再等下一轮，比常驻高光更"活"） */
.exam-cd::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 32%,
    color-mix(in srgb, #fff 24%, transparent) 48%,
    transparent 64%
  );
  transform: translateX(-130%);
  animation: cd-sheen 5.4s var(--ease) 1.4s infinite;
  pointer-events: none;
}
@keyframes cd-sheen {
  0%,
  58% {
    transform: translateX(-130%);
  }
  92%,
  100% {
    transform: translateX(130%);
  }
}
/* 呼吸光晕：天数越少，跳得越快 */
.exam-cd::after {
  content: '';
  position: absolute;
  inset: -40% -20%;
  background: radial-gradient(
    60% 60% at 50% 50%,
    color-mix(in srgb, var(--accent) 22%, transparent),
    transparent 70%
  );
  opacity: 0.5;
  animation: cd-breathe 3.6s var(--ease) infinite alternate;
  pointer-events: none;
}
.tier-hot::after {
  animation-duration: 2.4s;
}
.tier-final::after {
  animation-duration: 1.3s;
  background: radial-gradient(
    60% 60% at 50% 50%,
    color-mix(in srgb, var(--gold) 30%, transparent),
    transparent 70%
  );
}
@keyframes cd-breathe {
  from {
    opacity: 0.24;
    transform: scale(0.94);
  }
  to {
    opacity: 0.62;
    transform: scale(1.06);
  }
}
.cd-kicker {
  position: relative;
  z-index: 1;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: color-mix(in srgb, var(--accent) 62%, var(--ink-3));
}
.cd-main {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  gap: 5px;
}
.cd-num {
  font-size: 42px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: -0.02em;
  background: var(--accent-grad);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.tier-final .cd-num {
  background: linear-gradient(145deg, var(--gold), var(--accent));
  -webkit-background-clip: text;
  background-clip: text;
}
.cd-unit {
  font-size: 12px;
  color: var(--ink-2);
}
.cd-date {
  margin-left: 2px;
  font-size: 10.5px;
  color: var(--ink-3);
}

/* ---------- 窄屏：顶栏紧凑 chip ---------- */
.exam-cd.compact {
  position: static;
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  min-width: 0;
  padding: 4px 9px;
  border-radius: 999px;
  opacity: 1;
  transform: none;
}
:global(body.app-ready .exam-cd.compact) {
  transform: none;
}
.compact .cd-kicker {
  font-size: 10.5px;
  letter-spacing: 0.08em;
}
.compact .cd-num {
  font-size: 17px;
}
.compact .cd-unit {
  font-size: 10.5px;
}
.compact::after,
.compact::before {
  display: none;
}
</style>
