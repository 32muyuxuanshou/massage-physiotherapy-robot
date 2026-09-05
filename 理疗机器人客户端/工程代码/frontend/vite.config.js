import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 添加服务器配置
  server: {
    host: true,        // 监听所有网络接口，解决连接问题
    port: 5173,        // 指定端口（可选，默认就是5173）
  }
})
