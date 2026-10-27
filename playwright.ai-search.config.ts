import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests', testMatch: ['ai-home-search.spec.ts', 'google-maps-final-acceptance.spec.ts'], workers: 1,
  timeout: 45_000, expect: { timeout: 7000 }, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:4175', trace: 'retain-on-failure' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4175',
    env: { ...process.env, VITE_ENABLE_MOCK_MODE: '1', VITE_GOOGLE_MAPS_TEST_SDK: '1', VITE_API_BASE_URL: '/api/v1' },
    url: 'http://127.0.0.1:4175', reuseExistingServer: false,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
