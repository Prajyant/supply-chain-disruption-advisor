import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ingest': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/risks': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/chat': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/network': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/shipments': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/agents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/vessels': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/node/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path: string) => path,
      },
      '/weather': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/graph': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/playbooks': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/feedback': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
