/**
 * 显示字体（思源宋体）单独成模块，好让它脱离关键 CSS 阻塞链。
 * 由 main.js 动态 import —— Vite 会把这四份 @font-face 拆成独立 CSS chunk，
 * 运行时注入，启动屏就不必先解析完 486KB 字体声明才画得出来。
 * 分片本身（每份 101 条 unicode-range）要保留：真正的字形下载是按需命中的。
 */
import '@fontsource/noto-serif-sc/500.css'
import '@fontsource/noto-serif-sc/600.css'
import '@fontsource/noto-serif-sc/700.css'
import '@fontsource/noto-serif-sc/900.css'
