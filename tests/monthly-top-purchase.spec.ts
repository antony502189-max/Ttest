import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/payments/listings/*/top/availability?*', route => {
    const hours = Number(new URL(route.request().url()).searchParams.get('durationHours'))
    expect([12, 24, 72]).toContain(hours)
    return route.fulfill({ json: { municipalityCode: '28079', municipality: 'Madrid', capacity: 3,
      available: true, availableSlots: 3, availableAt: null, serverNow: new Date().toISOString() } })
  })
})

test('TOP preserves the chosen listing and charges only the explicitly selected hourly tier', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  let paid = 0
  await page.route('**/payments/listings/*/top/checkout', route => {
    expect(route.request().postDataJSON()).toEqual({ durationHours: 72 })
    paid++
    return route.fulfill({ status: 503, json: { detail: 'Stripe is not configured' } })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/mis-anuncios', { waitUntil: 'domcontentloaded' })
  await expect(page.getByTestId('owner-top-cta')).toHaveCount(0)
  await expect(page.locator('.owner-homepage-cta')).toHaveCount(0)
  const card = page.locator('.manage-card').filter({ has: page.getByTestId('owner-top-promote-button') }).first()
  const selectedId = await card.getAttribute('data-listing-id')
  await card.getByTestId('owner-top-promote-button').click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByRole('heading', { name: 'Promocionar anuncio' })).toBeVisible()
  await expect(dialog).not.toContainText('4,50')
  await expect(dialog.getByRole('button', { name: 'Pagar con Stripe' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Sube tu anuncio a TOP', exact: false }).click()
  await expect(dialog.locator(`[data-listing-id="${selectedId}"]`)).toHaveClass(/is-selected/)
  const options = dialog.locator('.owner-promotion-duration-option')
  await expect(options).toHaveCount(3)
  await expect(options.nth(0)).toContainText('12 horas')
  await expect(options.nth(0)).toContainText('0,99')
  await expect(options.nth(1)).toContainText('24 horas')
  await expect(options.nth(1)).toContainText('1,70')
  await expect(options.nth(2)).toContainText('3 días')
  await expect(options.nth(2)).toContainText('4,50')
  await expect(options.nth(0)).toHaveAttribute('aria-pressed', 'true')
  await expect(dialog.locator('input[type="date"]')).toHaveCount(0)
  await options.nth(2).click()
  await expect(options.nth(2)).toHaveAttribute('aria-pressed', 'true')
  await dialog.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(dialog).toContainText('4,50')
  expect(paid).toBe(0)
  await dialog.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(paid).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
