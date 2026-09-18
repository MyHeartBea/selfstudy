<script setup>
/**
 * ShaderBackdrop —— WebGL 噪声场背景（用户要求"Shader 背景、粒子/噪声场"）
 * ===========================================================================
 * 与 v2 原有 AmbientLayer 的关系：
 *   AmbientLayer 用 CSS 渐变 + 墨团 + 浮尘做氛围，**不占用 GPU 上下文**，
 *   是"稳"的方案。这里补一个 **WebGL 噪声场**作为可选加强层，
 *   因为它能做出 CSS 做不到的东西：缓慢流动的噪声、随滚动的场变化、
 *   随指针的局部偏移 —— 也就是"活着"的背景。
 *
 * 但必须处理三个现实问题（否则会拖慢整站）：
 *   ① **GPU 争用**：v2 已有大量 DOM 背景层。所以本层：
 *      · devicePixelRatio 上限 1.5（不追 2x/3x）
 *      · 分辨率按 0.75 缩放渲染（噪声本身模糊，看不出差别，但省 40% 像素）
 *      · 页面隐藏 / 组件卸载时立刻停止 rAF
 *      · 只在 >= 900px 宽启用（窄屏用 AmbientLayer 就够）
 *   ② **降级**：拿不到 WebGL 上下文 / prefers-reduced-motion 时**什么都不画**，
 *      直接隐藏自己（不会留下黑块）。
 *   ③ **主题适配**：颜色从 v2 的 CSS 变量读出来传进 shader，
 *      所以亮/暗主题切换时背景跟着变（不是写死的）。
 *
 * 用法：在 AppLayout 里渲染这个组件（放在 AmbientLayer 之后即可）。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const el = ref(null)

let gl = null
let program = null
let raf = 0
let running = false
let startTime = 0
let uniforms = {}
let resizeHandler = null
let moveHandler = null
let visibilityHandler = null

const VERT = `
attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
`

// 简化的 value-noise：三层不同频率的噪声叠加 + 极慢流动。
// 不用完整的 simplex（代码量大、收益小），value noise 足以做"场"。
const FRAG = `
precision mediump float;
uniform vec2  u_res;
uniform float u_time;
uniform float u_scroll;
uniform vec2  u_mouse;
uniform vec3  u_bg;
uniform vec3  u_tint;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i + vec2(0.0, 0.0)), hash(i + vec2(1.0, 0.0)), u.x),
    mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  // 刻意不用 for 循环的比较写法：比较符号会被 Vue 的 SFC 解析器
  // 当成标签开头而编译报错。用 do/while + 计数器达到同样效果
  // （GLSL ES 1.0 支持，且循环上界固定，移动端也安全）。
  int i = 0;
  do {
    v += a * noise(p);
    p *= 2.02;
    a *= 0.5;
    i += 1;
  } while (i != 4);
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 p = uv * 2.6 + u_mouse * 0.06;

  // 三层缓慢流动的噪声，纵向随滚动偏移 —— 形成"场在移动"
  float n1 = fbm(p + vec2(u_time * 0.015, u_scroll * 0.6));
  float n2 = fbm(p * 1.9 - vec2(u_time * 0.011, u_scroll * 0.35));
  float field = n1 * 0.65 + n2 * 0.35;

  // 只在角落附近显影，中间保持干净（不抢内容可读性）
  vec2 c = uv - vec2(0.86, 0.12);
  float corner = exp(-dot(c, c) * 7.0);
  vec2 c2 = uv - vec2(0.08, 0.92);
  float corner2 = exp(-dot(c2, c2) * 9.0);

  vec3 col = u_bg;
  col += u_tint * field * (corner * 0.5 + corner2 * 0.28) * 1.5;

  // 极轻的暗角，给版面一点纵深
  float vig = smoothstep(1.25, 0.25, length(uv - 0.5));
  col *= mix(0.94, 1.0, vig);

  gl_FragColor = vec4(col, 1.0);
}
`

/** 从 CSS 变量读颜色（支持 #rrggbb 与 rgb()） */
function readColor(name, fallback) {
  try {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    if (!v) return fallback
    if (v.startsWith('#')) {
      const hex = v.slice(1)
      const full =
        hex.length === 3
          ? hex
              .split('')
              .map((c) => c + c)
              .join('')
          : hex
      return [
        parseInt(full.slice(0, 2), 16) / 255,
        parseInt(full.slice(2, 4), 16) / 255,
        parseInt(full.slice(4, 6), 16) / 255,
      ]
    }
    const m = v.match(/(\d+(?:\.\d+)?)/g)
    if (m && m.length >= 3) {
      return [Number(m[0]) / 255, Number(m[1]) / 255, Number(m[2]) / 255]
    }
  } catch {
    /* 读不到就用兜底 */
  }
  return fallback
}

function compile(type, src) {
  const sh = gl.createShader(type)
  gl.shaderSource(sh, src)
  gl.compileShader(sh)
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) return null
  return sh
}

onMounted(() => {
  const canvas = el.value
  if (!canvas) return
  // 窄屏不启用（省 GPU；窄屏用 AmbientLayer 就够）
  if (900 > window.innerWidth) return
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return

  gl = canvas.getContext('webgl', {
    antialias: false,
    alpha: true,
    depth: false,
    stencil: false,
    powerPreference: 'low-power',
  })
  if (!gl) {
    canvas.classList.add('is-off')
    return
  }

  const vs = compile(gl.VERTEX_SHADER, VERT)
  const fs = compile(gl.FRAGMENT_SHADER, FRAG)
  if (!vs || !fs) {
    canvas.classList.add('is-off')
    return
  }
  program = gl.createProgram()
  gl.attachShader(program, vs)
  gl.attachShader(program, fs)
  gl.linkProgram(program)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    canvas.classList.add('is-off')
    return
  }
  gl.useProgram(program)

  const buf = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, buf)
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  )
  const loc = gl.getAttribLocation(program, 'a_pos')
  gl.enableVertexAttribArray(loc)
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0)

  for (const name of ['u_res', 'u_time', 'u_scroll', 'u_mouse', 'u_bg', 'u_tint']) {
    uniforms[name] = gl.getUniformLocation(program, name)
  }

  let mx = 0.5
  let my = 0.5
  let tmx = 0.5
  let tmy = 0.5

  const resize = () => {
    // 分辨率按 0.75 缩放：噪声本身模糊，看不出差别，但省 40% 像素
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    const w = Math.max(1, Math.floor(window.innerWidth * dpr * 0.75))
    const h = Math.max(1, Math.floor(window.innerHeight * dpr * 0.75))
    canvas.width = w
    canvas.height = h
    gl.viewport(0, 0, w, h)
    gl.uniform2f(uniforms.u_res, w, h)
  }

  const applyColors = () => {
    const bg = readColor('--bg', [0.96, 0.945, 0.91])
    const accent = readColor('--accent', [0.76, 0.29, 0.19])
    gl.uniform3fv(uniforms.u_bg, bg)
    gl.uniform3fv(uniforms.u_tint, accent)
  }

  const onMove = (e) => {
    tmx = e.clientX / window.innerWidth
    tmy = e.clientY / window.innerHeight
  }

  resizeHandler = () => {
    resize()
    applyColors()
  }
  moveHandler = onMove
  resize()
  applyColors()
  window.addEventListener('resize', resizeHandler, { passive: true })
  window.addEventListener('pointermove', moveHandler, { passive: true })

  startTime = performance.now()
  running = true
  const frame = () => {
    if (!running) return
    const t = (performance.now() - startTime) / 1000
    mx += (tmx - mx) * 0.04
    my += (tmy - my) * 0.04
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight)
    gl.uniform1f(uniforms.u_time, t)
    gl.uniform1f(uniforms.u_scroll, Math.min(1, window.scrollY / max))
    gl.uniform2f(uniforms.u_mouse, mx - 0.5, my - 0.5)
    gl.drawArrays(gl.TRIANGLES, 0, 6)
    raf = requestAnimationFrame(frame)
  }
  raf = requestAnimationFrame(frame)

  // 页面隐藏时停 rAF（后台标签页不该继续吃 GPU）
  visibilityHandler = () => {
    if (document.visibilityState === 'hidden') {
      running = false
      cancelAnimationFrame(raf)
    } else if (!running) {
      running = true
      startTime = performance.now()
      raf = requestAnimationFrame(frame)
    }
  }
  document.addEventListener('visibilitychange', visibilityHandler)
})

onBeforeUnmount(() => {
  running = false
  cancelAnimationFrame(raf)
  // 之前这里移除的是 resizeHandler —— 但注册的是内层 resize，指针完全不同，
  // 等于每次挂载都漏一个 resize + 一个 pointermove 监听器。
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  if (moveHandler) window.removeEventListener('pointermove', moveHandler)
  if (visibilityHandler) document.removeEventListener('visibilitychange', visibilityHandler)
  gl = null
  program = null
})
</script>

<template>
  <canvas ref="el" class="shader-backdrop" aria-hidden="true"></canvas>
</template>

<style scoped>
.shader-backdrop {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
  display: block;
  /* 与 AmbientLayer 叠在一起会更柔；单独用时也成立 */
  opacity: 0.9;
}
/*
  CSS 兜底场：WebGL 拿不到上下文 / 着色器编译失败时，脚本会给 canvas 加 .is-off。
  那时用这层渐变顶上 —— 保证任何环境下背景都不空，
  且用的是 v2 自己的渐变语言（不是随手一块色）。
  实测无头环境会走这条路径，所以这层是必要的，不是可选项。
*/
.shader-backdrop.is-off {
  display: block !important;
  opacity: 0.75;
  background:
    radial-gradient(
      60% 45% at 88% 8%,
      color-mix(in srgb, var(--accent) 16%, transparent),
      transparent 62%
    ),
    radial-gradient(
      50% 40% at 4% 96%,
      color-mix(in srgb, var(--accent) 9%, transparent),
      transparent 60%
    );
}
@media (prefers-reduced-motion: reduce) {
  .shader-backdrop {
    display: none;
  }
}
</style>
