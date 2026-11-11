import { defineConfig } from '@playwright/test'
import base from '../playwright.province.config'

export default defineConfig({
  ...base,
  testDir: '../tests',
  testMatch: ['municipality-search.spec.ts', 'a11y.spec.ts', 'master-task-visual.spec.ts', 'external-availability.spec.ts'],
  use: { ...base.use, baseURL: 'http://127.0.0.1:4191' },
  webServer: {
    ...base.webServer,
    cwd: process.cwd(),
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4191 --strictPort',
    url: 'http://127.0.0.1:4191',
  },
})
