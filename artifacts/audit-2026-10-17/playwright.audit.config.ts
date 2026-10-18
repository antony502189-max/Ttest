import { defineConfig } from '@playwright/test'
import base from '../../playwright.config'

export default defineConfig({
  ...base,
  testDir: '.',
  testMatch: ['province-suite.audit.spec.ts'],
  outputDir: './browser-results',
  reporter: [['list'], ['json', { outputFile: './browser-results.json' }]],
  use: { ...base.use, baseURL: 'http://127.0.0.1:4174' },
  webServer: undefined,
})
