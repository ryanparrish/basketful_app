import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const cartBasePath = env.VITE_BASE_PATH || '/new/cart/'

  return {
    plugins: [react()],
    base: mode === 'production' ? cartBasePath : '/',
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
