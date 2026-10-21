import { defineConfig } from '@playwright/test'
import base from './playwright.config'

export default defineConfig({
  ...base,
  testMatch: ['province-top.spec.ts', 'municipality-search.spec.ts', 'spain-community-search.spec.ts', 'owner-promotion-flow.spec.ts', 'audit-remediation.spec.ts'],
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4173',
    env: { ...process.env, VITE_ENABLE_MOCK_MODE: '1', VITE_GOOGLE_MAPS_TEST_SDK: '1' },
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 120000,
  },
})
