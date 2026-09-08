import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('customer video fixes stay traceable to the observed regression contract', () => {
  const audit = readFileSync('docs/audit/customer-video-2026-09-09.md', 'utf8')
  expect(audit).toContain('in-flight state must never be represented as an authoritative empty list')
  expect(audit).toContain('Fresh untouched legacy location defaults are converted to an explicit unresolved state')
})
