import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests', testMatch: 'ai-registered-entry.spec.ts', workers: 1,
  timeout: 45000, expect: { timeout: 10000 }, reporter: 'list',
  outputDir: 'output/registered-ai-browser-results',
  use: { baseURL: 'http://127.0.0.1:4184', trace: 'retain-on-failure' },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4184',
    env: { ...process.env, VITE_PUBLIC_AI_BETA: '1', VITE_AI_REGISTERED_SEARCH: '1', VITE_ENABLE_MOCK_MODE: '0', VITE_GOOGLE_MAPS_TEST_SDK: '1' },
    url: 'http://127.0.0.1:4184', reuseExistingServer: false,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], permissions: ['microphone'], launchOptions: {
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}),
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
  } } }],
})
