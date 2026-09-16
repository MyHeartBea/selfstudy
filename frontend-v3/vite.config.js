/**
 * v3 构建配置 —— 夜航星图（Nocturnal Atlas）
 *
 * 与 v2 的关键差异：
 *  1. **base 可切**：默认 '/'（挂在后端根路径）。但 v3 需要能与 v2 并行访问，
 *     所以支持 BASE_PATH 覆盖（例如 '/v3/'）。这让"并行上线"不需要改任何代码。
 *  2. **dev 端口 5175**：v2 用 5174，两者可同时起，互不干扰。
 *  3. **分包**：vue/router/axios 之外全部懒加载；GSAP、KaTeX 独立 chunk（阶段 1 起启用）。
 *  4. 代理 /api 与 /images 到同一个后端 8000 —— v2/v3 共用一份数据。
 */
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const BASE = process.env.BASE_PATH || '/'
/** 构建时间戳：设置页用它回答"我现在跑的是哪一版"（并行期自查用） */
const BUILD_TIME = new Date().toISOString().slice(0, 16).replace('T', ' ')

export default defineConfig({
  base: BASE,
  plugins: [vue()],
  define: {
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
  },
  test: {
    // DOM 级测试需要浏览器环境（与 v2 一致）
    environment: 'happy-dom',
    include: ['tests/**/*.test.js'],
    globals: false,
  },
  server: {
    host: '127.0.0.1',
    port: Number(process.env.V3_PORT) || 5175,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/images': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    // 体积预算：阶段 5 会把它接进 CI（超过阈值直接失败）
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('katex')) return 'katex'
            if (id.includes('gsap')) return 'motion'
            if (id.includes('lucide')) return 'icons'
            if (id.includes('vue') || id.includes('axios')) return 'vendor'
          }
        },
      },
    },
  },
})
