import { expect, test } from '@playwright/test'

const quote = { available: true, endsAt: null, reservedListingId: null, featuredListingId: null, amountCents: 495, currency: 'EUR', offers: [{ durationHours: 12, amountCents: 495 }, { durationHours: 24, amountCents: 850 }, { durationHours: 72, amountCents: 2250 }] }
for (const [language, width, labels] of [
  ['ru', 320, { top: 'Поднять свое объявление в ТОП', home: 'Закрепить на главной', back: 'Назад' }],
  ['en', 390, { top: 'Move your listing to TOP', home: 'Feature on the homepage', back: 'Back' }],
  ['es', 1280, { top: 'Sube tu anuncio a TOP', home: 'Destacar en portada', back: 'Volver' }],
] as const) {
  test(`promotion choices retain the site design and return without charging: ${language} at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript((locale) => {
      localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', locale)
    }, language)
    let checkouts = 0
    await page.route('**/payments/homepage/quote', route => route.fulfill({ json: quote }))
    await page.route('**/payments/listings/*/*/checkout', route => { checkouts++; return route.fulfill({ status: 503, json: { detail: 'Test only' } }) })
    await page.goto('/#/mis-anuncios')
    await expect(page.locator('.owner-top-cta')).toHaveCount(0)
    await page.getByTestId('owner-top-promote-button').first().click()
    let dialog = page.getByRole('dialog')
    await expect(dialog).toHaveClass(/owner-top-dialog/)
    await expect(dialog.locator('.owner-promotion-choice')).toHaveCount(2)
    await expect(dialog).not.toContainText(/60\s*€|4[.,]95|8[.,]50|22[.,]50/)
    await dialog.getByRole('button', { name: new RegExp(labels.home) }).click()
    dialog = page.getByRole('dialog')
    await expect(dialog.locator('.owner-promotion-price')).toContainText(/4[.,]95/)
    await dialog.getByRole('button', { name: labels.back, exact: true }).click()
    await expect(page.getByTestId('owner-promotion-choices')).toBeVisible()
    await expect(page.getByRole('dialog')).not.toContainText(/4[.,]95|8[.,]50|22[.,]50/)
    expect(checkouts).toBe(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.getByRole('dialog').screenshot({ path: `output/advertising/promotion-choice-${language}.png` })
  })
}

test('occupied homepage keeps the selected listing and prevents checkout', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.route('**/payments/homepage/quote', route => route.fulfill({ json: { ...quote, available: false, endsAt: '2027-01-01T00:00:00Z' } }))
  await page.goto('/#/mis-anuncios')
  await page.getByTestId('owner-top-promote-button').first().click()
  await page.getByRole('button', { name: /Destacar en portada/ }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('La portada está ocupada')
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toBeDisabled()
})
