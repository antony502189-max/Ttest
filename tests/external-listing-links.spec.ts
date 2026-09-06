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

test('external mobile result uses the same lime source CTA treatment as requirement chips and keeps native links', async ({ page }) => {
  await page.addInitScript((listing) => {
    localStorage.setItem('112233:listings:v3', JSON.stringify({ version: 3, data: [listing] }))
  }, externalListing)
  await finishOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()

  const card = page.locator('.m2-result-card').first()
  await expect(card).toHaveAttribute('data-listing-id', externalListing.id)

  const resultSourceCta = card.locator('.m2-external-source-cta')
  await expect(resultSourceCta).toBeVisible()
  await expect(resultSourceCta).toContainText('Consultar con el anunciante')
  await expect(resultSourceCta).toHaveAttribute('role', 'link')
  await expect(resultSourceCta).toHaveAttribute('data-external-source-url', externalListing.sourceUrl)
  const ctaStyle = await resultSourceCta.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      borderTopWidth: style.borderTopWidth,
      borderTopColor: style.borderTopColor,
      backgroundColor: style.backgroundColor,
      color: style.color,
      cursor: style.cursor,
    }
  })
  expect(ctaStyle).toEqual({
    borderTopWidth: '2px',
    borderTopColor: 'rgb(132, 169, 0)',
    backgroundColor: 'rgb(228, 242, 163)',
    color: 'rgb(48, 70, 0)',
    cursor: 'pointer',
  })
  await expectExternalPopup(page, () => resultSourceCta.click())
  await expectExternalPopup(page, () => card.locator('.m2-result-card__image-button').click())

  await page.getByRole('button', { name: /Mapa/i }).click()
  await expect(page.getByTestId('google-map')).toBeVisible()
  await page.locator('.m2-listing-marker').first().click()
  const preview = page.getByTestId('mobile-map-listing-preview')
  await expect(preview).toBeVisible()

  const sourceImage = preview.locator('.m2-map-listing-preview__media')
  const sourceCta = preview.locator('.m2-map-listing-preview__open')
  await expect(sourceImage).toHaveAttribute('href', externalListing.sourceUrl)
  await expect(sourceImage).toHaveAttribute('target', '_blank')
  await expect(sourceCta).toHaveAttribute('href', externalListing.sourceUrl)
  await expect(sourceCta).toHaveAttribute('target', '_blank')
  await expectExternalPopup(page, () => sourceCta.click())
})

test('internal listing similar cards do not render the long lime top rule', async ({ page }) => {
  await finishOnboarding(page)
  await page.goto('/#/habitacion/arme%C3%B1ime-luminosa-01')

  const similarCard = page.locator('.idealista-listing-page .listing-similar .property-card').first()
  await expect(similarCard).toBeVisible()
  const borderTopWidth = await similarCard.evaluate((element) => getComputedStyle(element).borderTopWidth)
  expect(borderTopWidth).toBe('0px')
})
