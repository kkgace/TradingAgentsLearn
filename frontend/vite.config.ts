// TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端端口可经环境变量覆盖（VITE_API_PORT）；默认 8000。
// 例：本机 8000 被其他项目占用时，后端起 8001 并以 VITE_API_PORT=8001 启动本前端。
const API_PORT = process.env.VITE_API_PORT || '8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: `http://localhost:${API_PORT}`, changeOrigin: true },
      '/sse': { target: `http://localhost:${API_PORT}`, changeOrigin: true }
    }
  }
})
