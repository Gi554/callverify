import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api/portal': 'http://127.0.0.1:8090',
      '/api/assurance': 'http://127.0.0.1:8091',
      '/api/isolation': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api\/isolation/, '/api'),
      },
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
