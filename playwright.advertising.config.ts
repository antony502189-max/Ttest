import base from './playwright.config'
import { defineConfig } from '@playwright/test'

export default defineConfig({
  ...base,
  reporter: 'list',
  globalTimeout: 120_000,
  use: { ...base.use, baseURL: 'http://127.0.0.1:4193', video: 'off', trace: 'off' },
  testMatch: ['**/advertising-seven-slots.spec.ts', '**/commercial-advertising.spec.ts'],
  webServer: {
    ...base.webServer,
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4193',
    env: { ...process.env, VITE_ENABLE_MOCK_MODE: '1', VITE_GOOGLE_MAPS_TEST_SDK: '1' },
    url: 'http://127.0.0.1:4193',
    reuseExistingServer: true,
  },
})
