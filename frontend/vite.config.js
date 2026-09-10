import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 研错本前端：开发端口 5174，接口代理到本机 8000 的后端（生产模式后端直接挂载 dist）
export default defineConfig({
  plugins: [vue()],
  // 组件层（DOM）测试需要浏览器环境：给卡片点击、弹窗等交互做回归
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.test.js'],
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/images': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          katex: ['katex'],
        },
      },
    },
  },
})
