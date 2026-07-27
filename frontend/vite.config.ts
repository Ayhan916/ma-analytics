import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyConfig = {
  '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: (p: string) => p.replace(/^\/api/, '') },
}

export default defineConfig({
  plugins: [react()],
  server:  { proxy: proxyConfig },
  preview: { proxy: proxyConfig },
})
