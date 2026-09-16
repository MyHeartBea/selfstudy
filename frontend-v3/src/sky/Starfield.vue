/** * 星点场（Starfield）—— 夜航星图的"最远层" *
--------------------------------------------------------------------------- * 只用 WebGL
做**它擅长的事**：大量星点的闪烁 + 按亮度视差。 * * 为什么星云不在这里画：实测四轮着色器方案（exp
衰减 / 只抖中心 / 域扭曲 / * 解析梯度雾团）都会在放大后留下肉眼可见硬边，而柔和的背景雾气用 CSS 多层
* radial-gradient + blur 天生软边且零 GPU 成本。所以职责分离： * CSS 管"柔"（.aurora），WebGL
管"锐"（星点）。 * * 性能与降级： * - prefers-reduced-motion：不创建 WebGL，直接不渲染 * - 无
WebGL：静默返回（CSS 雾气仍在，页面不会变成纯黑） * - 页面不可见时暂停 rAF（切标签页不烧电） * -
移动端星点数量与 DPR 减半 */
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const canvas = ref(null)

let gl = null
let program = null
let buffers = null
let quadBuffer = null
let raf = 0
let starCount = 0
let running = false
let bgProgram = null
let bgResLoc = null
let timeLoc = null
let mouseLoc = null
let quadPosLoc = -1

const state = { dpr: 1, w: 0, h: 0, mx: 0, my: 0, tmx: 0, tmy: 0, t0: 0 }

/* ── 着色器 ──────────────────────────────────────────────────────────────── */
const VERT = `
attribute vec2 a_p;
attribute float a_s;     // 星等（0–1）：越大越亮越近
attribute float a_ph;    // 闪烁相位
attribute vec3  a_c;     // 颜色（科目色系）
uniform float u_time;
uniform vec2  u_mouse;
varying float v_a;
varying vec3  v_c;
void main() {
  vec2 p = a_p;
  // 视差：亮星（近）随指针位移更多；不改变布局，只改裁剪坐标
  p += u_mouse * 0.014 * (0.35 + a_s);
  gl_Position = vec4(p, 0.0, 1.0);
  float tw = 0.62 + 0.38 * sin(u_time * (0.45 + a_ph * 1.7) + a_ph * 30.0);
  v_a = tw * (0.32 + a_s * 0.68);
  v_c = a_c;
  gl_PointSize = max(1.0, a_s * 2.6 + 1.0);
}
`

const FRAG_POINT = `
precision mediump float;
varying float v_a;
varying vec3  v_c;
void main() {
  vec2 d = gl_PointCoord - 0.5;
  float r = length(d);
  float a = smoothstep(0.5, 0.0, r) * v_a;
  gl_FragColor = vec4(v_c * a, a);
}
`

/* 背景层：极暗底 + 若隐若现的高频颗粒（不含任何大尺度噪声，避免菱形面片） */
const VERT_QUAD = `
attribute vec2 a_pos;
void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }
`
const FRAG_BG = `
precision mediump float;
uniform vec2 u_res;
float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 col = vec3(0.015, 0.016, 0.024);
  col += vec3(0.012, 0.012, 0.018) * (hash(floor(uv * u_res / 2.0)) - 0.5);
  gl_FragColor = vec4(col, 1.0);
}
`

function compile(type, src) {
  const sh = gl.createShader(type)
  gl.shaderSource(sh, src)
  gl.compileShader(sh)
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    if (import.meta.env.DEV) console.warn('[starfield] shader', gl.getShaderInfoLog(sh))
    return null
  }
  return sh
}

function link(vsSrc, fsSrc) {
  const vs = compile(gl.VERTEX_SHADER, vsSrc)
  const fs = compile(gl.FRAGMENT_SHADER, fsSrc)
  if (!vs || !fs) return null
  const p = gl.createProgram()
  gl.attachShader(p, vs)
  gl.attachShader(p, fs)
  gl.linkProgram(p)
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return null
  return p
}

/* 科目色系：与设计令牌一致（红移橙 / 矿脉青 / 琥珀 / 紫 / 中性星白） */
const PALETTE = [
  [1.0, 0.36, 0.24],
  [0.36, 0.78, 0.85],
  [0.88, 0.7, 0.35],
  [0.56, 0.48, 0.94],
  [0.91, 0.9, 0.98],
]

function buildStars() {
  const narrow = window.innerWidth < 900
  starCount = narrow ? 240 : 620
  const P = new Float32Array(starCount * 2)
  const S = new Float32Array(starCount)
  const PH = new Float32Array(starCount)
  const C = new Float32Array(starCount * 3)

  for (let i = 0; i < starCount; i++) {
    P[i * 2] = Math.random() * 2 - 1
    P[i * 2 + 1] = Math.random() * 2 - 1
    const r = Math.random()
    // 星等分布：大量暗星 + 少量亮星，才是真实星空的感觉
    S[i] = r > 0.965 ? 1 : r > 0.84 ? 0.6 : r > 0.5 ? 0.3 : 0.14
    PH[i] = Math.random()
    const c = PALETTE[Math.random() < 0.12 ? (Math.random() * PALETTE.length) | 0 : 4]
    C[i * 3] = c[0]
    C[i * 3 + 1] = c[1]
    C[i * 3 + 2] = c[2]
  }

  const bind = (data, name, size) => {
    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW)
    const loc = gl.getAttribLocation(program, name)
    if (loc >= 0) {
      gl.enableVertexAttribArray(loc)
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0)
    }
    return buf
  }

  gl.useProgram(program)
  buffers = {
    p: bind(P, 'a_p', 2),
    s: bind(S, 'a_s', 1),
    ph: bind(PH, 'a_ph', 1),
    c: bind(C, 'a_c', 3),
    // 记下属性位置：每帧重新绑定时要用（见 frame() 里的踩坑注释）
    loc: {
      p: gl.getAttribLocation(program, 'a_p'),
      s: gl.getAttribLocation(program, 'a_s'),
      ph: gl.getAttribLocation(program, 'a_ph'),
      c: gl.getAttribLocation(program, 'a_c'),
    },
  }
}

function resize() {
  const el = canvas.value
  if (!el || !gl) return
  const narrow = window.innerWidth < 900
  state.dpr = Math.min(window.devicePixelRatio || 1, narrow ? 1.5 : 1.75)
  state.w = Math.floor(window.innerWidth * state.dpr)
  state.h = Math.floor(window.innerHeight * state.dpr)
  el.width = state.w
  el.height = state.h
  gl.viewport(0, 0, state.w, state.h)
  gl.useProgram(bgProgram)
  gl.uniform2f(bgResLoc, state.w, state.h)
}

function frame(now) {
  if (!running) return
  const t = (now - state.t0) / 1000
  // 指针 lerp：一切带阻尼，没有一步是瞬移
  state.mx += (state.tmx - state.mx) * 0.05
  state.my += (state.tmy - state.my) * 0.05

  /* 背景层：**每次都重新绑定四边形缓冲**。
     踩过的坑：vertexAttribPointer 绑定的是"当前 ARRAY_BUFFER"，而不是"某个程序的属性"。
     建完星点缓冲后当前 ARRAY_BUFFER 变成了星点位置，此时直接 drawArrays 会把星点数据
     当四边形读 —— 表现就是画布全黑（实测 readPixels 全 0）。 */
  gl.useProgram(bgProgram)
  gl.disable(gl.BLEND)
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer)
  gl.enableVertexAttribArray(quadPosLoc)
  gl.vertexAttribPointer(quadPosLoc, 2, gl.FLOAT, false, 0, 0)
  gl.drawArrays(gl.TRIANGLES, 0, 6)

  if (program) {
    gl.useProgram(program)
    gl.enable(gl.BLEND)
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE)
    // 同理：切回星点程序前重新绑定星点缓冲
    gl.bindBuffer(gl.ARRAY_BUFFER, buffers.p)
    gl.enableVertexAttribArray(buffers.loc.p)
    gl.vertexAttribPointer(buffers.loc.p, 2, gl.FLOAT, false, 0, 0)
    gl.uniform1f(timeLoc, t)
    gl.uniform2f(mouseLoc, state.mx, state.my)
    gl.drawArrays(gl.POINTS, 0, starCount)
  }
  raf = requestAnimationFrame(frame)
}

function onPointer(e) {
  state.tmx = (e.clientX / window.innerWidth - 0.5) * 2
  state.tmy = -(e.clientY / window.innerHeight - 0.5) * 2
}

function onVisibility() {
  if (document.hidden) {
    running = false
    cancelAnimationFrame(raf)
  } else if (!running && gl) {
    running = true
    state.t0 = performance.now() - 1000 // 续上时间轴，避免跳变
    raf = requestAnimationFrame(frame)
  }
}

onMounted(() => {
  const el = canvas.value
  if (!el) return
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return // 降级：不建上下文

  gl = el.getContext('webgl', {
    antialias: false,
    alpha: false,
    depth: false,
    stencil: false,
    powerPreference: 'high-performance',
  })
  if (!gl) return // 无 WebGL：静默退出，CSS 雾气兜底

  bgProgram = link(VERT_QUAD, FRAG_BG)
  program = link(VERT, FRAG_POINT)
  if (!bgProgram) return
  if (bgProgram) {
    bgResLoc = gl.getUniformLocation(bgProgram, 'u_res')
  }
  if (program) {
    timeLoc = gl.getUniformLocation(program, 'u_time')
    mouseLoc = gl.getUniformLocation(program, 'u_mouse')
  }
  // 背景三角形：单独保存缓冲与属性位置，每帧重新绑定（见 frame() 注释）
  quadBuffer = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuffer)
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  )
  gl.useProgram(bgProgram)
  quadPosLoc = gl.getAttribLocation(bgProgram, 'a_pos')
  gl.enableVertexAttribArray(quadPosLoc)
  gl.vertexAttribPointer(quadPosLoc, 2, gl.FLOAT, false, 0, 0)

  if (program) buildStars()
  resize()

  state.t0 = performance.now()
  state.mx = state.tmx = 0
  state.my = state.tmy = 0
  running = true
  raf = requestAnimationFrame(frame)

  window.addEventListener('resize', resize, { passive: true })
  window.addEventListener('pointermove', onPointer, { passive: true })
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  running = false
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', resize)
  window.removeEventListener('pointermove', onPointer)
  document.removeEventListener('visibilitychange', onVisibility)
  // 释放 GPU 资源：长会话里反复进出页面不会累积
  if (gl) {
    Object.values(buffers || {}).forEach((b) => gl.deleteBuffer(b))
    if (program) gl.deleteProgram(program)
    if (bgProgram) gl.deleteProgram(bgProgram)
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    gl = null
  }
})
</script>

<template>
  <canvas ref="canvas" class="starfield" aria-hidden="true"></canvas>
</template>

<style scoped>
.starfield {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: var(--z-sky);
  pointer-events: none;
}
</style>
