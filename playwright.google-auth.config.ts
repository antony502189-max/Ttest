import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: 'google-auth.spec.ts',
  timeout: 30_000,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:4174' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4174',
    env: { ...process.env, VITE_ENABLE_MOCK_MODE: '0', VITE_GOOGLE_CLIENT_ID: 'test-google-client.apps.googleusercontent.com' },
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [{ name: 'chromium', use: devices['Desktop Chrome'] }],
})
