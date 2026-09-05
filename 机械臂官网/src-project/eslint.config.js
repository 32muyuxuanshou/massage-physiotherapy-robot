import js from '@eslint/js'
import globals from 'globals'
import pluginJs from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import { defineConfig } from 'eslint/config'

export default defineConfig([
  {
    files: ['**/*.{js,mjs,cjs,vue}'],
    plugins: { js },
    extends: ['js/recommended'],
    languageOptions: { globals: globals.browser },
  },
  pluginVue.configs['flat/essential'],
  // your config
  {
    plugins: {
      vue: pluginVue,
    },
    rules: {
      ...pluginVue.configs['base'].rules,
    },
  },
  {
    plugins: {
      '@eslint/js': pluginJs,
    },
    rules: {
      ...pluginJs.configs.recommended.rules,
      'vue/multi-word-component-names': 0, // 关闭组件名称必须为多单词
    },
  },
  {
    name: 'custom-lint-config',
    files: ['*.js'],
    rules: {
      'no-undef': 'off', // 使用字符串而不是数字来表示规则的严重性
    },
  },
])
