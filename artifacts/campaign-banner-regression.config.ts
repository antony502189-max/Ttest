import { defineConfig } from '@playwright/test'
import base from '../playwright.config'

export default defineConfig({
  ...base,
  testDir: '../tests',
  use: { ...base.use, baseURL: 'http://127.0.0.1:4192' },
  webServer: {
    ...base.webServer,
    cwd: process.cwd(),
    command: 'node node_modules/vite/bin/vite.js build && node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4192 --strictPort',
    url: 'http://127.0.0.1:4192',
  },
})
