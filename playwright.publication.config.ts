import { defineConfig, devices } from '@playwright/test'

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH

export default defineConfig({
  testDir: './tests',
  testMatch: 'listing-publication-errors.spec.ts',
  timeout: 60_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4175',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4175',
    env: {
      ...process.env,
      VITE_API_BASE_URL: '/api/v1',
      VITE_E2E_BYPASS_ONBOARDING: '1',
      VITE_ENABLE_MOCK_MODE: '0',
      VITE_GOOGLE_MAPS_TEST_SDK: '1',
    },
    url: 'http://127.0.0.1:4175',
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [{
    name: 'chromium',
    use: {
      ...devices['Desktop Chrome'],
      ...(executablePath ? { launchOptions: { executablePath } } : {}),
    },
  }],
})
