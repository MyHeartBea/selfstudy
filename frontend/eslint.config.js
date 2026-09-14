// ESLint 扁平配置（ESLint v10）。目标：只抓真问题，不做风格大改。
// 风格交给 Prettier，所以末尾用 prettier 配置关掉与格式化冲突的规则。
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettierConfig from '@vue/eslint-config-prettier'
import globals from 'globals'

export default [
  {
    // 构建产物、依赖、字体子集不参与检查；Playwright 产物同理
    ignores: [
      'dist/**',
      'node_modules/**',
      'coverage/**',
      'public/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },

  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],

  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.es2021,
      },
    },
    rules: {
      // 只抓真问题：未使用变量/未定义变量/可疑写法
      // caughtErrors: 'none' —— 本项目的约定是 `catch (err) { /* 说明 */ }`：
      // 错误已由 axios 拦截器统一提示，这里刻意静默，故不把 catch 形参算作未使用。
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
        },
      ],
      'no-undef': 'error',
      'no-console': 'off',
      // 允许 `catch {}`（裸 catch 是合法写法），但仍禁止 `try { ... } catch {}` 以外的空块
      'no-empty': ['error', { allowEmptyCatch: true }],

      // Vue：这些在项目里是刻意用法或噪音，关掉
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/first-attribute-linebreak': 'off',
      // 保留有价值的正确性规则
      'vue/no-unused-vars': 'error',
      'vue/no-unused-components': 'warn',
      'vue/no-mutating-props': 'error',
      'vue/require-v-for-key': 'error',
      'vue/no-use-v-if-with-v-for': 'error',
      'vue/no-parsing-error': 'error',
    },
  },

  {
    // 这三处 v-html 是刻意且安全的：
    // - Icon.vue：注入的是 icons.js 里写死的 SVG 字符串（无外部输入）
    // - MathText.vue / RichText.vue：注入的是 KaTeX 渲染结果与自建 Markdown 渲染器输出，
    //   KaTeX 默认 trust=false；用户/AI 文本在渲染前已做过 HTML 转义（见 utils/markdown.js）
    files: ['src/ui/Icon.vue', 'src/components/MathText.vue', 'src/components/RichText.vue'],
    rules: {
      'vue/no-v-html': 'off',
    },
  },

  {
    // 测试文件：vitest 全局 + 允许长文件
    files: ['tests/**/*.js'],
    languageOptions: {
      globals: { ...globals.node, ...globals.browser },
    },
  },

  {
    // E2E（Playwright）：跑在 Node 里，但 page.evaluate 回调里是浏览器环境
    files: ['e2e/**/*.js', 'playwright.config.js'],
    languageOptions: {
      globals: { ...globals.node, ...globals.browser },
    },
  },

  // Prettier 兜底：关闭所有与格式化冲突的规则（必须放最后）
  prettierConfig,
]
