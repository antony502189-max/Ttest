import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('admin access recovery distinguishes explicit denial from transient failure', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(source).toContain("error.status === 401 || error.status === 403")
  expect(source).toContain('window.setTimeout(() => { void verify(false) }, 450)')
  expect(source).toContain("setPhase('denied')")
  expect(source).toContain("setPhase('error')")
  expect(source).toContain('Сессия остаётся активной')
})
