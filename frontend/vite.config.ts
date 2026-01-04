import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // 监听所有网络接口，允许局域网访问
    port: 5173, // Vue开发服务器端口（固定端口）
    strictPort: true, // 如果端口被占用，报错而不是自动切换（确保使用固定端口）
    proxy: {
      // 代理所有以 /api 开头的请求到后端服务器
      '/api': {
        target: 'http://localhost:8000', // FastAPI后端地址（固定端口8000）
        changeOrigin: true, // 改变请求头中的origin
        secure: false, // 如果是https接口，需要配置这个参数
      }
    }
  }
})
