import { expect, test } from '@playwright/test'
import { adminRentalModeLabel, matchesAdminRentalMode } from '../src/lib/admin-listings'
import { translateText } from '../src/contexts/i18n-context'

test('admin rental mode labels distinguish long and short stays', () => {
  expect(adminRentalModeLabel('long')).toBe('Larga estancia')
  expect(adminRentalModeLabel('holiday')).toBe('Corta estancia')
  expect(translateText(adminRentalModeLabel('long'), 'ru')).toBe('Долгосрочная аренда')
  expect(translateText(adminRentalModeLabel('holiday'), 'ru')).toBe('Краткосрочная аренда')
})

test('admin rental mode filter keeps only requested rental type', () => {
  expect(matchesAdminRentalMode('long', '')).toBe(true)
  expect(matchesAdminRentalMode('holiday', '')).toBe(true)
  expect(matchesAdminRentalMode('long', 'long')).toBe(true)
  expect(matchesAdminRentalMode('holiday', 'long')).toBe(false)
  expect(matchesAdminRentalMode('holiday', 'holiday')).toBe(true)
  expect(matchesAdminRentalMode('long', 'holiday')).toBe(false)
})
