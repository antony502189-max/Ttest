import { defineConfig, devices } from '@playwright/test'

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH

export default defineConfig({
  testDir: './tests/phase1',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'output/playwright/search-lifecycle', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4176',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4176 --strictPort',
    url: 'http://127.0.0.1:4176',
    reuseExistingServer: false,
    env: { VITE_ENABLE_MOCK_MODE: '0', VITE_GOOGLE_MAPS_TEST_SDK: '1', VITE_API_BASE_URL: '/api/v1', VITE_E2E_BYPASS_ONBOARDING: '1' },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } } }],
})
