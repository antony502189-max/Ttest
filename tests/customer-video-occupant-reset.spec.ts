import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

function hashParams(url: string) {
  const hash = new URL(url).hash
  const queryIndex = hash.indexOf('?')
  return new URLSearchParams(queryIndex >= 0 ? hash.slice(queryIndex + 1) : '')
}

async function openOccupantSheet(page: Page) {
  await page.locator('.m2-occupant-trigger').click()
  const sheet = page.locator('.m2-custom-occupant-sheet')
  await expect(sheet).toBeVisible()
  return sheet
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear()
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto('/')
})

test('CUSTOMER-VIDEO pets narrows results, back preserves it, unrestricted resets the catalog and reload', async ({ page }) => {
  const mode = page.locator('.m2-mode-switch > button').first()
  await mode.click()
  await expect(mode).toHaveClass(/is-active/)

  let sheet = await openOccupantSheet(page)
  const onePerson = sheet.locator('[data-m2-occupant-key="one"]')
  const pets = sheet.locator('[data-m2-occupant-key="pets"]')
  await onePerson.click()
  await pets.click()
  await expect(onePerson).toHaveAttribute('aria-checked', 'true')
  await expect(pets).toHaveAttribute('aria-checked', 'true')
  await sheet.locator('.m2-custom-occupant-done').click()

  await page.getByTestId('open-location').click()
  const petResults = page.getByTestId('mobile-results')
  await expect(petResults).toBeVisible()
  const petCount = await petResults.locator('.m2-result-card').count()
  expect(petCount).toBeGreaterThan(0)
  expect(petCount).toBeLessThan(23)
  const narrowedParams = hashParams(page.url())
  expect(narrowedParams.get('mascotas')).toBe('Sí')
  expect(narrowedParams.get('capacidad')).toBe('1')
  expect(narrowedParams.get('requisito')).toBe('single-person')

  await petResults.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)

  sheet = await openOccupantSheet(page)
  await expect(sheet.locator('[data-m2-occupant-key="one"]')).toHaveAttribute('aria-checked', 'true')
  await expect(sheet.locator('[data-m2-occupant-key="pets"]')).toHaveAttribute('aria-checked', 'true')
  const unrestricted = sheet.locator('[data-m2-occupant-key="unrestricted"]')
  await unrestricted.click()
  await expect(unrestricted).toHaveAttribute('aria-checked', 'true')
  await expect(sheet.locator('[data-m2-occupant-key="one"]')).toHaveAttribute('aria-checked', 'false')
  await expect(sheet.locator('[data-m2-occupant-key="pets"]')).toHaveAttribute('aria-checked', 'false')
  await sheet.locator('.m2-custom-occupant-done').click()

  await page.getByTestId('open-location').click()
  const unrestrictedResults = page.getByTestId('mobile-results')
  await expect(unrestrictedResults).toBeVisible()
  await expect(unrestrictedResults.locator('.m2-result-card')).toHaveCount(23)

  const params = hashParams(page.url())
  for (const key of ['mascotas', 'ninos', 'capacidad', 'requisito', 'requisitos']) {
    expect(params.get(key), `${key} must be cleared by Sin restricciones`).toBeNull()
  }
  expect(params.get('alquiler')).toBe('long')

  await page.reload()
  await expect(page.getByTestId('mobile-results').locator('.m2-result-card')).toHaveCount(23)
  const reloaded = hashParams(page.url())
  for (const key of ['mascotas', 'ninos', 'capacidad', 'requisito', 'requisitos']) {
    expect(reloaded.get(key), `${key} must stay cleared after reload`).toBeNull()
  }
})
