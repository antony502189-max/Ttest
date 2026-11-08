import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests', testMatch: ['ai-private-demo.spec.ts'], workers: 1, timeout: 30000,
  outputDir: 'output/private-demo-browser-results',
  use: { baseURL: 'http://127.0.0.1:4177' },
  webServer: { command: 'node scripts/serve-ai-private-demo.mjs', url: 'http://127.0.0.1:4177',
    reuseExistingServer: false, timeout: 90000 },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: {
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}),
  } } }],
})
