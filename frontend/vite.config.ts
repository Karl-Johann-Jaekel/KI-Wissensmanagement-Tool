import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // Only BACKEND_PORT is read from the repo-root .env; nothing is exposed to the bundle.
  const rootEnv = loadEnv(mode, '..', '')
  const backendPort = rootEnv.BACKEND_PORT ?? '8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': `http://127.0.0.1:${backendPort}`,
      },
    },
  }
})
