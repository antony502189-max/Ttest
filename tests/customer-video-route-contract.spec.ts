import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('customer video routes are wrapped by the correct recovery gates', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  expect(app).toContain('<ProtectedRoute><OwnedListingsHydrationGate><MyListingsPage /></OwnedListingsHydrationGate></ProtectedRoute>')
  expect(app).toContain('<ProtectedRoute><AdminAccessRecoveryGate><AdminPage /></AdminAccessRecoveryGate></ProtectedRoute>')
})
