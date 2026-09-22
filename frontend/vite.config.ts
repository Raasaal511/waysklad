import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        // NetworkFirst для read-эндпоинтов — экран продажи открывается даже офлайн,
        // хоть и с последними закэшированными товарами/остатками. Не кэшируем мутации.
        runtimeCaching: [
          {
            urlPattern: /\/api\/(products|inventory|counterparties)(\/|\?|$)/,
            method: 'GET',
            handler: 'NetworkFirst',
            options: {
              cacheName: 'waysklad-api-read',
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      manifest: {
        name: 'WaySklad',
        short_name: 'WaySklad',
        description: 'Товарный учёт, продажи и долги для малого бизнеса',
        theme_color: '#1f5c3f',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },    }),
  ],
  server: {
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // WebSocket-канал уведомлений (GET /api/notifications/ws)
      },
      '/uploads': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // vite preview — тот же прокси, что и dev-сервер, чтобы можно было гонять
  // Lighthouse/QA-скрипты по production-сборке с реальным backend (P7 п.2).
  preview: {
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/uploads': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
