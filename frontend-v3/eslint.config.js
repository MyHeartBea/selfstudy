// v3 ESLint 扁平配置（与 v2 同一标准，目标：只抓真问题，不做风格大改）。
// 风格交给 Prettier，末尾用 prettier 配置关掉与格式化冲突的规则。
import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettierConfig from '@vue/eslint-config-prettier'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'public/**'],
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
        // 构建期由 vite define 注入的常量（见 vite.config.js 的 define）
        __BUILD_TIME__: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' },
      ],
      'no-undef': 'error',
      'no-console': 'off',
      'no-empty': ['error', { allowEmptyCatch: true }],

      // Vue：与 v2 相同的取舍（项目里这些是刻意用法或噪音）
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/no-unused-vars': 'error',
      'vue/no-unused-components': 'warn',
      'vue/no-mutating-props': 'error',
      'vue/require-v-for-key': 'error',
      'vue/no-use-v-if-with-v-for': 'error',
      'vue/no-parsing-error': 'error',
    },
  },

  {
    // 测试与配置文件跑在 Node 里；page.evaluate 之类回调里则是浏览器环境
    files: ['tests/**/*.js', 'vite.config.js'],
    languageOptions: {
      globals: { ...globals.node, ...globals.browser },
    },
  },

  // Prettier 兜底：必须放最后
  prettierConfig,
]
