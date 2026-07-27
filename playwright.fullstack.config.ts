import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/full-stack',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'output/playwright/full-stack-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4174',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4174',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      VITE_API_BASE_URL: 'http://127.0.0.1:8000/api/v1',
      VITE_E2E_BYPASS_ONBOARDING: '1',
      VITE_ENABLE_MOCK_MODE: '0',
    },
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chromium', use: { ...devices['iPhone 13'], viewport: { width: 390, height: 844 } } },
  ],
})
