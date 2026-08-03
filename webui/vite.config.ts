import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The FastAPI backend (server.py) runs on :8000 and owns /ws, /api and /static.
// In dev we proxy those to it so the Vite dev-server can hot-reload the UI.
const BACKEND = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // highlight.js (via rehype-highlight) is the bulk; it is needed for chat code
    // rendering and is fully local, so we accept the size rather than lazy-split it.
    chunkSizeWarningLimit: 900,
  },
  server: {
    proxy: {
      '/ws': { target: BACKEND, ws: true },
      '/api': { target: BACKEND },
      '/static': { target: BACKEND },
    },
  },
})
