import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests', testMatch: ['ai-lab-runtime.spec.ts', 'ai-map-refresh-review.spec.ts'], workers: 1, timeout: 30000,
  outputDir: 'output/ai-lab-contract-test-results',
  use: { baseURL: 'http://127.0.0.1:4176' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --mode ai-synthetic-lab --host 127.0.0.1 --port 4176',
    env: { ...process.env, VITE_AI_CLOSED_LAB: 'decision-transport-fixture', VITE_AI_LAB_SOURCE_SHA: 'a'.repeat(40),
      VITE_ENABLE_MOCK_MODE: '1', VITE_GOOGLE_MAPS_TEST_SDK: '1', VITE_API_BASE_URL: '/api/v1' },
    url: 'http://127.0.0.1:4176', reuseExistingServer: false,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: {
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}),
  } } }],
})
