import { defineConfig } from '@playwright/test'
const port = Number(process.env.ADMIN_TEST_PORT ?? '4197')

export default defineConfig({
  testDir: './tests/admin-performance',
  timeout: 240_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: 'list',
  use: { baseURL: `http://127.0.0.1:${port}`, viewport: { width: 1440, height: 900 } },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port}`,
    env: { VITE_ENABLE_MOCK_MODE: '0', VITE_GOOGLE_MAPS_TEST_SDK: '1' },
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: !process.env.CI,
  },
})
