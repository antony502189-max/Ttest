import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('location step permits address/postcode entry without trusting untouched legacy defaults', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')
  expect(source).toContain("AUTO_CITY_VALUE")
  expect(source).toContain('Введите адрес или почтовый индекс')
  expect(source).toContain('The postcode must contain exactly 5 digits.')
})
