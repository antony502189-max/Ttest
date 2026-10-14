import { expect, test } from '@playwright/test'

test('monthly TOP uses the existing dialog and submits only the fixed monthly package', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.route('**/payments/homepage/quote', route => route.fulfill({ json: { available: true, endsAt: null } }))
  let paid = 0
  await page.route('**/payments/listings/*/top/checkout', route => {
    expect(route.request().postDataJSON()).toEqual({ days: 30 })
    paid++
    return route.fulfill({ status: 503, json: { detail: 'Stripe is not configured' } })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/mis-anuncios', { waitUntil: 'domcontentloaded' })
  await page.getByTestId('owner-top-promote-button').first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('30 € · 1 mes en TOP')).toBeVisible()
  await expect(dialog.locator('select')).toHaveCount(0)
  expect(paid).toBe(0)
  await dialog.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(paid).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
