<script setup>
/**
 * 环境氛围层（墨韵 2.0）：底纱 → 旋转极光 → 视差光斑 → 呼吸墨渍 →
 * 远山剪影 → 墨字水印 → 纸纹噪点 → 暗角 → 浮尘；另含鼠标跟随柔光。
 * 纯展示层：fixed、pointer-events:none，动画走 CSS，视差走单个 rAF 循环。
 */
import { onMounted, onUnmounted, ref } from 'vue'

const ambientEl = ref(null)
const glowEl = ref(null)
let rafId = 0
let mx = 0, my = 0, gx = 0, gy = 0

function onMove(e) {
  mx = e.clientX
  my = e.clientY
}

onMounted(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  gx = mx = window.innerWidth / 2
  gy = my = window.innerHeight / 2
  // 浮尘：随机参数的小颗粒从底部缓缓升起
  if (!reduce && ambientEl.value) {
    for (let i = 0; i < 16; i++) {
      const d = document.createElement('span')
      d.className = 'amb-dust'
      const size = 2 + Math.random() * 3.5
      d.style.cssText =
        `left:${(Math.random() * 100).toFixed(1)}%;width:${size.toFixed(1)}px;height:${size.toFixed(1)}px;` +
        `--o:${(0.05 + Math.random() * 0.1).toFixed(2)};--dx:${(Math.random() * 120 - 60).toFixed(0)}px;` +
        `animation-duration:${(16 + Math.random() * 26).toFixed(1)}s;animation-delay:-${(Math.random() * 30).toFixed(1)}s`
      ambientEl.value.appendChild(d)
    }
  }
  if (!reduce) {
    const blobs = ambientEl.value
      ? [...ambientEl.value.querySelectorAll('[data-depth]')]
      : []
    const loop = () => {
      gx += (mx - gx) * 0.06
      gy += (my - gy) * 0.06
      if (glowEl.value) {
        glowEl.value.style.left = gx + 'px'
        glowEl.value.style.top = gy + 'px'
      }
      for (const b of blobs) {
        const depth = Number(b.dataset.depth) || 0
        b.style.translate = `${((gx / window.innerWidth - 0.5) * depth).toFixed(1)}px ${((gy / window.innerHeight - 0.5) * depth).toFixed(1)}px`
      }
      rafId = requestAnimationFrame(loop)
    }
    rafId = requestAnimationFrame(loop)
    window.addEventListener('mousemove', onMove, { passive: true })
  }
})

onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
  window.removeEventListener('mousemove', onMove)
})
</script>

<template>
  <div ref="ambientEl" class="ambient" aria-hidden="true">
    <div class="bgwash"></div>
    <div class="aurora"></div>
    <div class="amb-blob b1" data-depth="18"></div>
    <div class="amb-blob b2" data-depth="-26"></div>
    <div class="ink-blob ib1"></div>
    <div class="ink-blob ib2"></div>
    <div class="ink-blob ib3"></div>
    <svg class="mountains" viewBox="0 0 1440 220" preserveAspectRatio="none">
      <path d="M0 200 Q 180 90 360 150 T 720 130 T 1080 160 T 1440 120 V220 H0 Z" opacity=".5" />
      <path d="M0 220 Q 240 150 480 185 T 960 175 T 1440 190 V220 H0 Z" opacity=".8" />
    </svg>
    <div class="ink-char c1">研</div>
    <div class="ink-char c2">墨</div>
    <div class="grain"></div>
    <div class="vignette"></div>
  </div>
  <div ref="glowEl" class="cursor-glow" aria-hidden="true"></div>
</template>

<style scoped>
.ambient {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.9s var(--ease);
}
:global(body.app-ready .ambient) { opacity: 1; }

/* 底纱：多色渐变铺底 */
.bgwash {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1200px 800px at 85% -10%, var(--wash1), transparent 60%),
    radial-gradient(900px 620px at -10% 22%, var(--wash2), transparent 55%),
    radial-gradient(1000px 700px at 52% 112%, var(--wash3), transparent 62%),
    linear-gradient(180deg, var(--bg) 0%, var(--bg-soft) 100%);
}

/* 旋转极光 */
.aurora {
  position: absolute;
  inset: -45%;
  background: conic-gradient(
    from 0deg,
    transparent 0deg, var(--blob1) 60deg, transparent 130deg,
    var(--blob2) 200deg, transparent 260deg, var(--blob3) 310deg, transparent 360deg
  );
  filter: blur(110px);
  opacity: var(--aurora-o);
  animation: aurora-spin 70s linear infinite;
}
@keyframes aurora-spin { to { transform: rotate(360deg); } }

/* 视差光斑 */
.amb-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  will-change: transform;
}
.b1 { width: 560px; height: 560px; top: -160px; right: -80px; background: radial-gradient(circle at 40% 40%, var(--blob1), transparent 65%); animation: drift1 26s ease-in-out infinite alternate; }
.b2 { width: 640px; height: 640px; bottom: -220px; left: -160px; background: radial-gradient(circle at 60% 40%, var(--blob2), transparent 65%); animation: drift2 34s ease-in-out infinite alternate; }
@keyframes drift1 { from { transform: translate(0, 0) scale(1); } to { transform: translate(-70px, 60px) scale(1.15); } }
@keyframes drift2 { from { transform: translate(0, 0) scale(1.08); } to { transform: translate(90px, -70px) scale(0.94); } }

/* 呼吸墨渍 */
.ink-blob {
  position: absolute;
  filter: blur(26px);
  opacity: var(--deco);
  animation: ink-morph 18s ease-in-out infinite alternate;
}
.ink-blob::before {
  content: '';
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: radial-gradient(circle at 40% 40%, var(--bcol), transparent 70%);
}
.ib1 { width: 300px; height: 280px; top: -70px; left: 6%; border-radius: 62% 38% 55% 45% / 55% 48% 52% 45%; --bcol: var(--blob2); }
.ib2 { width: 340px; height: 300px; bottom: -90px; right: 4%; border-radius: 45% 55% 48% 52% / 52% 62% 38% 48%; --bcol: var(--blob1); animation-duration: 24s; }
.ib3 { width: 190px; height: 170px; top: 36%; right: 11%; border-radius: 52% 48% 42% 58% / 45% 52% 48% 55%; --bcol: var(--blob3); animation-duration: 30s; }
@keyframes ink-morph {
  0% { transform: rotate(0deg) scale(1); border-radius: 62% 38% 55% 45% / 55% 48% 52% 45%; }
  50% { transform: rotate(7deg) scale(1.08); border-radius: 45% 55% 48% 52% / 52% 62% 38% 48%; }
  100% { transform: rotate(-6deg) scale(0.95); border-radius: 52% 48% 42% 58% / 45% 52% 48% 55%; }
}

/* 远山剪影 */
.mountains { position: absolute; bottom: 0; left: 0; width: 100%; height: 220px; opacity: 0.05; }
[data-theme='dark'] .mountains { opacity: 0.08; }
.mountains path { fill: var(--ink); }

/* 墨字水印 */
.ink-char {
  position: absolute;
  font-family: var(--font-display);
  font-weight: 900;
  color: var(--ink);
  opacity: 0.04;
  line-height: 1;
  user-select: none;
}
.c1 { font-size: 24vw; top: -7vw; right: 0; transform: rotate(4deg); }
.c2 { font-size: 16vw; bottom: -4vw; left: 26vw; transform: rotate(-3deg); opacity: 0.028; }

/* 纸纹噪点 */
.grain {
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .03 0'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* 暗角 */
.vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 95% at 50% 42%, transparent 58%, var(--vig) 100%);
}

/* 浮尘 */
:deep(.amb-dust),
.amb-dust {
  position: absolute;
  border-radius: 50%;
  background: var(--ink);
  opacity: 0;
  animation: dust-up linear infinite;
  will-change: transform, opacity;
}
@keyframes dust-up {
  0% { transform: translateY(105vh) translateX(0); opacity: 0; }
  12% { opacity: var(--o); }
  85% { opacity: var(--o); }
  100% { transform: translateY(-8vh) translateX(var(--dx)); opacity: 0; }
}

/* 鼠标跟随柔光 */
.cursor-glow {
  position: fixed;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  z-index: 1;
  pointer-events: none;
  background: radial-gradient(circle, color-mix(in srgb, var(--accent) 8%, transparent), transparent 60%);
  transform: translate(-50%, -50%);
  left: -999px;
  top: -999px;
}
@media (max-width: 860px) {
  .cursor-glow { display: none; }
  .c2 { display: none; }
}
</style>
