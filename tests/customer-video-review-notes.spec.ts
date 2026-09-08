import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('customer video regression audit documents the exact observed failure modes', () => {
  const source = readFileSync('docs/audit/customer-video-2026-09-09.md', 'utf8')
  expect(source).toContain('/listings/mine')
  expect(source).toContain('Adeje / Armeñime / 38678')
  expect(source).toContain('401/403')
})
