import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ command }) => ({
  base: command === 'build' ? './' : '/',
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: parseInt(process.env.VITE_PORT || '80'),
    hmr: {
      // 支持通过反向代理访问时的HMR
      protocol: 'ws',
      host: 'localhost',
      port: parseInt(process.env.VITE_PORT || '80'),
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
}))
