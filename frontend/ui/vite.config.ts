import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Roteia chamadas de /api para o backend FastAPI, evitando CORS em dev
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // remove o prefixo /api ao encaminhar
        rewrite: (path) => path.replace(/^\/api/, ''),
      },

      // Roteia chamadas de /super para o backend FastAPI (super-admin)
      '/super': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
