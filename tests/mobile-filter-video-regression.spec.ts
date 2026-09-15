import { expect, test, type Page } from '@playwright/test'

const searchParams = (url: string) => {
  const hash = new URL(url).hash
  const index = hash.indexOf('?')
  return new URLSearchParams(index >= 0 ? hash.slice(index + 1) : '')
}

async function openOccupants(page: Page) {
  await page.locator('.m2-occupant-trigger').click()
  const sheet = page.locator('.m2-custom-occupant-sheet')
  await expect(sheet).toBeVisible()
  return sheet
}

async function backToHome(page: Page) {
  await page.locator('.m2-results__header > button').click()
  await expect(page.locator('.m2-home')).toBeVisible()
}

test.use({ viewport: { width: 390, height: 844 } })
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('video regression: rapid occupant changes end with a real unrestricted search', async ({ page }) => {
  await page.goto('/')
  const sheet = await openOccupants(page)
  const option = (key: string) => sheet.locator(`[data-m2-occupant-key="${key}"]`)

  for (const key of ['one', 'man', 'one', 'unrestricted', 'one', 'unrestricted']) {
    await option(key).click()
    await expect(option(key)).toHaveAttribute('aria-checked', 'true')
  }
  await sheet.locator('.m2-custom-occupant-done').click()
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()

  const params = searchParams(page.url())
  for (const key of ['requisito', 'capacidad', 'ninos', 'mascotas', 'fumar']) expect(params.get(key)).toBeNull()
  expect(await page.locator('.m2-result-card').count()).toBeGreaterThan(0)
})

test('same visible man filter gives the same non-empty result on repeated searches', async ({ page }) => {
  await page.goto('/')
  let sheet = await openOccupants(page)
  await sheet.locator('[data-m2-occupant-key="man"]').click()
  await expect(sheet.locator('[data-m2-occupant-key="man"]')).toHaveAttribute('aria-checked', 'true')
  await sheet.locator('.m2-custom-occupant-done').click()

  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  let params = searchParams(page.url())
  expect(params.get('requisito')).toBe('single-man')
  expect(params.get('capacidad')).toBe('1')
  const firstCount = await page.locator('.m2-result-card').count()
  expect(firstCount).toBeGreaterThan(0)

  await backToHome(page)
  sheet = await openOccupants(page)
  await expect(sheet.locator('[data-m2-occupant-key="man"]')).toHaveAttribute('aria-checked', 'true')
  await sheet.locator('.m2-custom-occupant-done').click()
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()

  params = searchParams(page.url())
  expect(params.get('requisito')).toBe('single-man')
  expect(params.get('capacidad')).toBe('1')
  expect(await page.locator('.m2-result-card').count()).toBe(firstCount)
})

test('home search clears hidden result-only filters instead of leaking them invisibly', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&capacidad=3&mascotas=No&fumar=No')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await backToHome(page)

  const sheet = await openOccupants(page)
  await expect(sheet.locator('[data-m2-occupant-key="unrestricted"]')).toHaveAttribute('aria-checked', 'true')
  await sheet.locator('.m2-custom-occupant-done').click()
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()

  const params = searchParams(page.url())
  expect(params.get('capacidad')).toBeNull()
  expect(params.get('mascotas')).toBeNull()
  expect(params.get('fumar')).toBeNull()
  expect(await page.locator('.m2-result-card').count()).toBeGreaterThan(0)
})
