import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

const externalListing = {
  id: 'external-idealista-123456', title: 'Habitación exterior en Adeje', city: 'Adeje', area: 'Adeje',
  approximateAddress: 'Adeje · ubicación aproximada', price: 710, monthlyPrice: 710, rentalMode: 'long',
  images: ['https://images.unsplash.com/photo-1524758631624-e2822e304c36?auto=format&fit=crop&w=800&q=80'],
  publishedAt: '2026-07-30T12:00:00.000Z', expiresAt: '2099-12-31', coordinates: { lat: 28.1227, lng: -16.7244 },
  isExternal: true, primarySource: 'Idealista', sourceUrl: 'https://www.idealista.com/inmueble/123456/', status: 'Publicado',
  sourcePriceText: '710 €/mes', contactPhone: '+34 612 345 678', contactWhatsapp: '+34 612 345 678',
  contactEmail: 'owner@example.test', roomSizeM2: 12, showPhone: true, showWhatsApp: true,
}

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
}

async function expectExternalPopup(page: Page, action: () => Promise<void>) {
  const popup = page.waitForEvent('popup')
  await action()
  await expect.poll(async () => (await popup).url()).toBe(externalListing.sourceUrl)
}

test('external mobile result and map preview open the original source', async ({ page }) => {
  await page.addInitScript((listing) => {
    localStorage.setItem('112233:listings:v3', JSON.stringify({ version: 3, data: [listing] }))
  }, externalListing)
  await finishOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()

  const card = page.locator('.m2-result-card').first()
  await expect(card).toHaveAttribute('data-listing-id', externalListing.id)
  await expectExternalPopup(page, () => card.locator('.m2-result-card__image-button').click())

  await page.getByRole('button', { name: /Mapa/i }).click()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await page.locator('.m2-listing-marker').first().click()
  const preview = page.getByTestId('mobile-map-listing-preview')
  await expect(preview).toBeVisible()
  await expectExternalPopup(page, () => preview.locator('.m2-map-listing-preview__open').click())
})
