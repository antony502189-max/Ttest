import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

const homeMode = (page: Page, index: 0 | 1) => page.locator('.m2-mode-switch > button').nth(index)

async function openHomeResults(page: Page, mode: 0 | 1) {
  await homeMode(page, mode).click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  return results
}

test('a new unrestricted home search clears stale advanced filters and preserves rental mode', async ({ page }) => {
  await finishOnboarding(page)

  const narrowed = await openHomeResults(page, 0)
  await narrowed.getByRole('button', { name: 'Filtros' }).click()
  await narrowed.getByLabel('Precio Máx').fill('500')
  await narrowed.getByLabel('Superficie Máx').fill('12')
  await narrowed.getByLabel('1 habitación').check()
  await narrowed.getByLabel('Habitaciones individuales').check()
  await expect(narrowed.getByRole('button', { name: /Ver anuncios · 6/ })).toBeVisible()
  await narrowed.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(narrowed.locator('.m2-result-card')).toHaveCount(6)

  await narrowed.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)
  await page.evaluate(() => localStorage.setItem('112233:listing-access-profile:v1', JSON.stringify({ occupant: 'any', pets: 'Cualquiera', smoking: 'Cualquiera' })))

  const unrestrictedLong = await openHomeResults(page, 0)
  await expect(unrestrictedLong.locator('.m2-result-card')).toHaveCount(23)
  const longUrl = new URL(page.url())
  const longParams = new URLSearchParams(longUrl.hash.split('?', 2)[1] ?? '')
  expect(longParams.get('precioMax')).toBeNull()
  expect(longParams.get('tamanoMax')).toBeNull()
  expect(longParams.get('tiposHabitacion')).toBeNull()
  expect(longParams.get('habitaciones')).toBeNull()
  expect(longParams.get('alquiler')).toBe('long')

  await unrestrictedLong.getByRole('button', { name: 'Volver' }).click()
  const unrestrictedHoliday = await openHomeResults(page, 1)
  await expect(unrestrictedHoliday.locator('.m2-result-card')).toHaveCount(9)
  const holidayUrl = new URL(page.url())
  const holidayParams = new URLSearchParams(holidayUrl.hash.split('?', 2)[1] ?? '')
  expect(holidayParams.get('alquiler')).toBe('holiday')
})
