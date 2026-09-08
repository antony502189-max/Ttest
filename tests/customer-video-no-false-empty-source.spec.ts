import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('owner page does not render false empty state before remote hydration completes', () => {
  const source = readFileSync('src/components/owned-listings-hydration-gate.tsx', 'utf8')
  expect(source).toContain("phase === 'checking'")
  expect(source).toContain('customer-owned-listings-loading')
  expect(source).toContain('sameUserSnapshot')
})
