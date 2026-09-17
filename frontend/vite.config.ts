import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { mobilePreviewPlugin } from './dev/mobilePreview.mjs'

const apiProxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [vue(), ...(mode === 'mobile' ? [mobilePreviewPlugin()] : [])],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: 5173,
    proxy: mode === 'mobile' ? {} : {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
        ws: true
      }
    }
  }
}))

