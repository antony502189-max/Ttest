import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('customer video regression suite covers owner hydration, location, localization and admin access', () => {
  const source = readFileSync('tests/customer-video-critical-regressions.spec.ts', 'utf8')
  expect(source).toContain('leaving a new publication does not make existing host listings disappear')
  expect(source).toContain('owned-listing empty state follows the selected UI language')
  expect(source).toContain('customer video fix removes the fake fresh-location claim')
  expect(source).toContain('customer video fix retries transient admin authorization')
})
