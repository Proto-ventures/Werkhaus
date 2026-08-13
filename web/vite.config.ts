import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // Root by default, because in production FastAPI serves this from `/` and a
  // build-time path is the one thing that cannot be fixed at runtime. Set
  // WERKHAUS_BASE when publishing the page somewhere it lives under a prefix —
  // GitHub Pages serves a project site from /<repo>/.
  base: process.env.WERKHAUS_BASE ?? '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    // Dev runs two processes: this, and uvicorn on :8000. The proxy means the
    // app only ever talks to its own origin, so there is no build-time backend
    // URL to get wrong when this is served from FastAPI in production.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/openapi.json': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/healthz': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
