/// <reference types="vitest" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // In dev the SPA calls /api on its own origin; Vite forwards it, so no CORS needed.
    proxy: { '/api': process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000' },
  },
  build: {
    rollupOptions: {
      output: {
        // The map engine is big; keep it in its own chunk so the form paints first.
        manualChunks: { maplibre: ['maplibre-gl', 'react-map-gl'], mui: ['@mui/material'] },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    css: false,
  },
});
