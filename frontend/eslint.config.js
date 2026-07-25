import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // 未声明变量直接报错（本次 autoTimer 事故的针对性防线）
      'no-undef': 'error',
      'no-unused-vars': 'warn',
      // 视图组件名为单词（Home/Dashboard 等），关闭多词限制
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    // Node 环境文件（构建配置、脚本）
    files: ['*.config.js', 'tests/**/*.mjs'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
]
