// Separate synthetic environment. No fallback to the current CRM API ports.
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  define: { 'import.meta.env.VITE_CRM_DEMO': JSON.stringify('true') },
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api/portal': 'http://127.0.0.1:8190',
      '/api/assurance': 'http://127.0.0.1:8191',
      '/api/isolation': {
        target: 'http://127.0.0.1:8100',
        rewrite: (path) => path.replace(/^\/api\/isolation/, '/api'),
      },
      '/api': 'http://127.0.0.1:8100',
    },
  },
})
