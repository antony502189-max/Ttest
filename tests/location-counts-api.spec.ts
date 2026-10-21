import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.route('**/api/v1/**', async (route) => {
    if (route.request().url().includes('/auth/refresh')) return route.fulfill({ status: 401, json: {} })
    await route.fulfill({ json: { items: [], total: 0, nextCursor: null, previousCursor: null, version: 'test' } })
  })
})

test('location counts use server totals and typing does not repeat the aggregate request', async ({ page }) => {
  let requests = 0
  await page.route('**/api/v1/listings/locations/counts', async (route) => {
    requests++
    await route.fulfill({ json: {
      items: [{ id: '38', count: 19 }], municipalities: [{ id: '38004', count: 7 }, { id: '38006', count: 12 }],
    } })
  })
  await page.goto('/#/?panel=ubicacion')
  await page.getByRole('searchbox').fill('Ar')
  await expect(page.getByTestId('municipality-option-38004')).toContainText('7 anuncios')
  await expect(page.getByTestId('municipality-option-38006')).toContainText('12 anuncios')
  await expect(page.getByTestId('municipality-option-38005')).toContainText('0 anuncios')
  const initialRequests = requests
  await page.getByRole('searchbox').fill('Arafo')
  await expect(page.getByTestId('municipality-option-38004')).toContainText('7 anuncios')
  expect(requests).toBe(initialRequests)
})

test('failed location counts show unavailable rather than an invented zero', async ({ page }) => {
  await page.route('**/api/v1/listings/locations/counts', (route) => route.fulfill({ status: 503, json: {} }))
  await page.goto('/#/?panel=ubicacion')
  await page.getByRole('searchbox').fill('Arafo')
  await expect(page.getByTestId('municipality-option-38004')).toContainText('— anuncios')
})
