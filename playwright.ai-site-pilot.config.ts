import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests', testMatch: ['ai-site-pilot.spec.ts', 'ai-voice-input.spec.ts'], workers: 1, timeout: 30000,
  outputDir: 'output/site-pilot-browser-results',
  use: { baseURL: 'http://127.0.0.1:4178/ai-pilot/' },
  webServer: { command: 'node scripts/serve-ai-site-pilot.mjs', url: 'http://127.0.0.1:4178/ai-pilot/',
    reuseExistingServer: false, timeout: 90000 },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions: {
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
    ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}),
  } } }],
})
