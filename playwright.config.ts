import { defineConfig, devices } from '@playwright/test'

const executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH

export default defineConfig({
  testDir: './tests',
  // Private/lab contracts require their dedicated Vite mode, not this ordinary
  // build. Both remain mandatory in the AI frontend CI dedicated configs.
  // These runtime-specific files run in their mandatory dedicated CI suites.
  testIgnore: ['**/ai-public-entry.spec.ts', 'full-stack/**', 'phase1/**', '**/tests/admin-performance/**', '**/google-auth.spec.ts', '**/listing-publication-errors.spec.ts', '**/location-counts-api.spec.ts', '**/ai-lab-runtime.spec.ts', '**/ai-private-demo.spec.ts', '**/ai-site-pilot.spec.ts', '**/ai-voice-input.spec.ts'],
  timeout: 60_000,
  expect: { timeout: 7_000 },
  snapshotPathTemplate: '{testDir}/visual-snapshots/{projectName}/{arg}{ext}',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { outputFolder: 'output/playwright/report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: executablePath ? 'off' : 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4173',
    env: { ...process.env, VITE_ENABLE_MOCK_MODE: '1', VITE_GOOGLE_MAPS_TEST_SDK: '1' },
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], ...(executablePath ? { launchOptions: { executablePath } } : {}) } }],
})
