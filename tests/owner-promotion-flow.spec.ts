import { expect, test } from '@playwright/test'

const quote = { available: true, endsAt: null, reservedListingId: null, featuredListingId: null, amountCents: 495, currency: 'EUR', offers: [{ durationHours: 12, amountCents: 495 }, { durationHours: 24, amountCents: 850 }, { durationHours: 72, amountCents: 2250 }] }
for (const [language, width, labels] of [
  ['ru', 320, { top: 'Поднять свое объявление в ТОП', home: 'Главный премиум-баннер', back: 'Назад' }],
  ['en', 390, { top: 'Move your listing to TOP', home: 'Main Premium Banner', back: 'Back' }],
  ['es', 1280, { top: 'Sube tu anuncio a TOP', home: 'Banner Premium Principal', back: 'Volver' }],
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
    const homepageChoice = dialog.locator('.owner-promotion-choice--homepage')
    const preview = homepageChoice.getByTestId('owner-homepage-promotion-preview')
    await expect(preview).toBeVisible()
    await expect(preview.locator('.owner-promotion-choice__preview-tile')).toHaveCount(2)
    await expect(preview.locator('.owner-promotion-choice__preview-photo img')).toBeVisible()
    await expect(preview.locator('.owner-promotion-choice__preview-tile--living .owner-promotion-choice__preview-tile-check svg')).toBeVisible()
    await expect(preview.locator('.owner-promotion-choice__preview-tile--holiday svg.owner-promotion-choice__preview-tile-icon')).toBeVisible()
    const previewText = {
      ru: ['КОМНАТЫ', 'ДОЛГОСРОЧНО', 'ТУРИЗМ'],
      en: ['ROOMS', 'LONG-TERM', 'TOURISM'],
      es: ['HABITACIONES', 'VIVIENDA', 'TURISMO'],
    }[language]
    await expect(preview.locator('.owner-promotion-choice__preview-tile-title')).toHaveText([previewText[0], previewText[0]])
    await expect(preview.locator('.owner-promotion-choice__preview-tile-subtitle')).toHaveText([previewText[1], previewText[2]])
    const chosenPhoto = await dialog.getByTestId('owner-top-option').locator('img').getAttribute('src')
    expect(chosenPhoto).toBeTruthy()
    await expect(preview.locator('img')).toHaveAttribute('src', chosenPhoto!)
    const cardLayout = await homepageChoice.evaluate((button) => {
      const image = button.querySelector('.owner-promotion-choice__preview')!.getBoundingClientRect()
      const copy = button.querySelector('.owner-promotion-choice__copy')!.getBoundingClientRect()
      const top = button.querySelector('.owner-promotion-choice__preview-photo')!.getBoundingClientRect()
      const bottom = button.querySelector('.owner-promotion-choice__preview-links')!.getBoundingClientRect()
      const green = button.querySelector('.owner-promotion-choice__preview-tile--living')!
      const pink = button.querySelector('.owner-promotion-choice__preview-tile--holiday')!
      return {
        imageWidth: image.width,
        aspectRatio: image.width / image.height,
        overlap: image.right > copy.left + 1,
        photoAboveTiles: top.bottom <= bottom.top + 1,
        greenBorder: getComputedStyle(green).borderTopColor,
        pinkBorder: getComputedStyle(pink).borderTopColor,
      }
    })
    expect(cardLayout.imageWidth).toBeGreaterThan(60)
    expect(cardLayout.aspectRatio).toBeGreaterThan(.85)
    expect(cardLayout.aspectRatio).toBeLessThan(.97)
    expect(cardLayout.overlap).toBe(false)
    expect(cardLayout.photoAboveTiles).toBe(true)
    expect(cardLayout.greenBorder).not.toBe(cardLayout.pinkBorder)
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
  await page.getByRole('button', { name: /Banner Premium Principal/ }).click()
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('La portada está ocupada')
  await expect(page.getByRole('button', { name: 'Pagar con Stripe' })).toBeDisabled()
})
