import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import eslint from 'vite-plugin-eslint'
import path from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ElementPlus from 'unplugin-element-plus/vite' // 导入element-plus的样式插件

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // 增加下面的配置项,这样在运行时就能检查eslint规范
    eslint({
      include: ['src/**/*.{js,vue}'], // 仅检查 src 目录下的文件
      lintOnStart: true, // 确保需要开启 LintOnStart
      cache: true, // 开启缓存以提高性能
    }),
    // element-plus自动导入插件
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
    ElementPlus({
      useSource: true,
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    paths: {
      '@/*': ['src/*'],
    },
  },
  server: { host: true, port: 8080 }, // 可以通过局域网内的其他设备访问该开发服务器。生产环境不适用
})
