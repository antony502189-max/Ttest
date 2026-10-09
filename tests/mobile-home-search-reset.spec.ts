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

const homeMode = (page: Page) => page.locator('.m2-mode-switch > button').first()

async function openHomeResults(page: Page) {
  await homeMode(page).click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  return results
}

test('unrestricted home search restores the full mode catalog after stale advanced filters', async ({ page }) => {
  await finishOnboarding(page)

  const narrowed = await openHomeResults(page)
  await narrowed.getByRole('button', { name: 'Filtros' }).click()
  await narrowed.getByLabel('Precio Máx').fill('500')
  await narrowed.getByLabel('Habitaciones individuales').check()
  const apply = narrowed.getByRole('button', { name: /Ver anuncios · \d+/ })
  await expect(apply).toBeVisible()
  const filteredCount = Number((await apply.textContent())?.match(/(\d+)$/)?.[1] ?? 0)
  expect(filteredCount).toBeGreaterThan(0)
  expect(filteredCount).toBeLessThan(23)
  await apply.click()
  await expect(narrowed.locator('.m2-result-card')).toHaveCount(filteredCount)

  await narrowed.getByRole('button', { name: 'Volver' }).click()
  await expect(narrowed.locator('.m2-result-card')).toHaveCount(23)
  await narrowed.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)
  await page.evaluate(() => localStorage.setItem('112233:listing-access-profile:v1', JSON.stringify({ occupant: 'any', pets: 'Cualquiera', smoking: 'Cualquiera' })))

  const unrestrictedLong = await openHomeResults(page, 0)
  await expect(unrestrictedLong.locator('.m2-result-card')).toHaveCount(23)
  const longParams = new URLSearchParams(new URL(page.url()).hash.split('?', 2)[1] ?? '')
  expect(longParams.get('precioMax')).toBeNull()
  expect(longParams.get('tamanoMax')).toBeNull()
  expect(longParams.get('tiposHabitacion')).toBeNull()
  expect(longParams.get('habitaciones')).toBeNull()
  expect(longParams.get('alquiler')).toBe('long')

  await unrestrictedLong.getByRole('button', { name: 'Volver' }).click()
  await expect(page.locator('.m2-mode-switch > button')).toHaveCount(1)
  await expect(page.getByRole('button', { name: /Turismo/ })).toHaveCount(0)
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&precioMax=5000')
  await expect(page).toHaveURL(/alquiler=long/)
  await expect(page.getByTestId('mobile-results')).toBeVisible()
})
