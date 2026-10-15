import { expect, test } from '@playwright/test'

test('TOP keeps the existing design, selects the clicked listing and shows service pricing only at confirmation', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.route('**/payments/homepage/quote', route => route.fulfill({ json: { available: true, endsAt: null } }))
  let paid = 0
  await page.route('**/payments/listings/*/top/checkout', route => {
    expect(route.request().postDataJSON()).toEqual({ days: 21 })
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
  await expect(dialog).not.toContainText('1 € al día')
  await expect(dialog).not.toContainText('60 €')
  await expect(dialog.getByRole('button', { name: 'Pagar con Stripe' })).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Sube tu anuncio a TOP', exact: false }).click()
  await expect(dialog.locator(`[data-listing-id="${selectedId}"]`)).toHaveClass(/is-selected/)
  await expect(dialog).not.toContainText('1 € al día')
  await dialog.getByLabel('Duración (mínimo 10 días)').fill('9')
  await expect(dialog.getByRole('button', { name: 'Continuar', exact: true })).toBeDisabled()
  await dialog.getByLabel('Duración (mínimo 10 días)').fill('21')
  await dialog.getByRole('button', { name: 'Continuar', exact: true }).click()
  await expect(dialog.getByText(/21 días.*21,00/)).toBeVisible()
  await page.route(`**/payments/listings/${selectedId}/top/checkout`, route => {
    expect(route.request().postDataJSON()).toEqual({ days: 21 })
    paid++
    return route.fulfill({ status: 503, json: { detail: 'Stripe is not configured' } })
  })
  await expect(dialog.locator('select')).toHaveCount(0)
  expect(paid).toBe(0)
  await dialog.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  expect(paid).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})
