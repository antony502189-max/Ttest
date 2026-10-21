import { defineConfig } from '@playwright/test'
import base from './playwright.province.config'

// Run against a built mock app when Vite's Windows dev server stalls on transforms.
// Build: VITE_ENABLE_MOCK_MODE=1 VITE_GOOGLE_MAPS_TEST_SDK=1 vite build --outDir output/municipality-search/mock-build
export default defineConfig({
  ...base,
  testMatch: ['municipality-search.spec.ts'],
  use: { ...base.use, baseURL: 'http://127.0.0.1:4187' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4187 --outDir output/municipality-search/mock-build',
    url: 'http://127.0.0.1:4187', reuseExistingServer: false,
  },
})
