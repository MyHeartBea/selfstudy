import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks: {
          // element-plus 不整包分包：让 rollup 按手动注册的组件 tree-shaking
          vue: ['vue', 'vue-router', 'axios', 'gsap'],
          katex: ['katex'],
        },
      },
    },
  },
})
