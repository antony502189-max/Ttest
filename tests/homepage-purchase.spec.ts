import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
})

test('homepage purchase selects an owned listing and opens Stripe only after explicit payment', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/payments/homepage/quote', route => route.fulfill({ json: { available: true, endsAt: null, reservedListingId: null, featuredListingId: null, amountCents: 6000, currency: 'EUR', months: 1 } }))
  let count = 0
  let target = ''
  await page.route('**/payments/listings/*/homepage/checkout', route => {
    count++
    target = route.request().url().split('/listings/')[1].split('/')[0]
    return route.fulfill({ status: 503, json: { detail: 'Stripe is not configured' } })
  })
  await page.goto('/#/mis-anuncios', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('.owner-homepage-cta')).toHaveCount(0)
  await expect(page.getByTestId('owner-top-cta')).toHaveCount(0)
  const card = page.locator('.manage-card').filter({ has: page.getByTestId('owner-top-promote-button') }).first()
  const listingId = await card.getAttribute('data-listing-id')
  await card.getByTestId('owner-top-promote-button').click()
  await expect(page.getByRole('dialog')).not.toContainText('60 €')
  await page.getByRole('button', { name: /Banner Premium Principal/ }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: 'Tu anuncio en portada' })).toBeVisible()
  await expect(dialog.locator('.owner-promotion-price')).toContainText('60,00')
  await expect(dialog.locator(`[data-listing-id="${listingId}"]`)).toBeVisible()
  expect(count).toBe(0)
  await expect(dialog.getByRole('button', { name: 'Pagar con Stripe' })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(count).toBe(1)
  expect(decodeURIComponent(target)).toBe(listingId)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('banner monthly total is visible before payment', async ({ page }) => {
  const id = '00000000-0000-4000-8000-000000000999'
  await page.route(`**/advertisements/${id}`, route => route.fulfill({ json: { id, title: 'Local service', description: 'Service for our community.', imageUrl: '', packageId: 'homepage_1d', status: 'pending_payment', paymentStatus: 'unpaid' } }))
  await page.route(`**/payments/advertisements/${id}/quote**`, route => {
    return route.fulfill({ json: { days: 30, months: 1, amountCents: 3000, currency: 'EUR', available: true } })
  })
  await page.goto(`/#/publicidad/${id}/checkout`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByLabel('Duración (mínimo 10 días)')).toHaveCount(0)
  await expect(page.locator('.ad-flow__price')).toContainText('30,00')
  await expect(page.locator('.ad-flow__price')).toContainText('1 mes')
  await expect(page.locator('.ad-flow__price')).not.toContainText('30 días')
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toBeEnabled()
})
