import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
      '/ui': 'http://localhost:8080',
    },
  },
  build: {
    outDir: 'dist',
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vue-runtime',
              test: /node_modules[\\/](vue|vue-router|vue-i18n)[\\/]/,
              priority: 2,
            },
            {
              name: 'primevue',
              test: /node_modules[\\/](@primevue|primevue|primeicons)[\\/]/,
              priority: 1,
            },
          ],
        },
      },
    },
  },
})
