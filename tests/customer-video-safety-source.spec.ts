import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('customer video fixes retain server authorization boundaries', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  expect(app).toContain('<ProtectedRoute><AdminAccessRecoveryGate><AdminPage /></AdminAccessRecoveryGate></ProtectedRoute>')
  expect(app).toContain('<ProtectedRoute><OwnedListingsHydrationGate><MyListingsPage /></OwnedListingsHydrationGate></ProtectedRoute>')
})
