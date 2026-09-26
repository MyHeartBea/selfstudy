import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { visualizer } from 'rollup-plugin-visualizer'

// 研错本前端：开发端口 5174，接口代理到本机 8000 的后端（生产模式后端直接挂载 dist）
// `npm run analyze`（vite build --mode analyze）时额外产出 dist/bundle-report.html
// —— bundle 组成此前从没可视化过，katex chunk 是否可按需没人验证过。
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    ...(mode === 'analyze'
      ? [
          visualizer({
            filename: 'dist/bundle-report.html',
            template: 'sunburst',
            gzipSize: true,
          }),
        ]
      : []),
  ],
  // 组件层（DOM）测试需要浏览器环境：给卡片点击、弹窗等交互做回归
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.test.js'],
  },
  server: {
    host: '127.0.0.1',
    // 端口可由 E2E_PORT 覆盖：Playwright 传入固定端口并用 --strictPort，避免静默换端口导致 baseURL 打空
    port: Number(process.env.E2E_PORT) || 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/images': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    // 字体一律不许内联成 base64：它们靠 unicode-range / 按需命中，
    // 内联等于把用不上的字形包塞进那支 CSS 一起下载。
    // 这里曾只挡了 woff/woff2，KaTeX 的 20 个 .ttf 照样被内联 —— katex CSS 709KB（源文件 23.8KB）。
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf|eot)$/.test(file) ? 0 : 4096),
    rollupOptions: {
      output: {
        // 之前只切了 katex，Vue 全家桶 + axios + 全部外壳组件混在一个
        // 219KB 的 index chunk 里：改一行文案就让用户重下整包，且首屏
        // 必须解析完所有外壳代码才拿得到运行时。
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('katex')) return 'katex'
          if (id.includes('gsap') || id.includes('lenis')) return 'motion'
          if (/[\\/](vue|vue-router|@vue|axios)[\\/]/.test(id)) return 'vendor'
        },
      },
    },
  },
}))
