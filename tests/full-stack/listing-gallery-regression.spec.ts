import { expect, test } from '@playwright/test'

const gallery = Array.from({ length: 5 }, (_, index) =>
  `/api/v1/media/00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`
)

function card(rentalMode: 'long' | 'holiday') {
  return {
    id: rentalMode === 'long'
      ? '10000000-0000-4000-8000-000000000001'
      : '20000000-0000-4000-8000-000000000001',
    title: rentalMode === 'long' ? 'Galería larga estancia' : 'Galería turística',
    city: 'Adeje',
    area: 'Playa de las Américas',
    approximateAddress: 'Playa de las Américas · ubicación aproximada',
    rentalMode,
    price: rentalMode === 'long' ? 725 : 55,
    roomType: 'Habitación individual',
    currentResidents: 1,
    roomCapacity: 1,
    bedroomCount: 2,
    roomSizeM2: 14,
    availableFrom: '2026-10-01',
    billsIncluded: true,
    restrictions: ['No fumar'],
    advertiserType: 'Particular',
    isExternal: false,
    sourceUrl: null,
    primarySource: null,
    sourcePriceText: null,
    pricePeriod: rentalMode === 'long' ? 'month' : 'night',
    priceIsFrom: false,
    publishedAt: '2026-09-30T00:00:00Z',
    promoted: false,
    coverImageUrl: gallery[0],
    imageUrls: gallery,
    description: 'Anuncio con cinco fotografías para comprobar la galería.',
  }
}

function detail(rentalMode: 'long' | 'holiday') {
  const base = card(rentalMode)
  return {
    ...base,
    ownerUserId: '30000000-0000-4000-8000-000000000001',
    owner: { name: 'Gallery Host', initials: 'GH', since: '2026-01-01T00:00:00Z', response: 'Consulta disponibilidad', verified: true },
    contactPhone: null,
    contactWhatsapp: null,
    contactEmail: null,
    showPhone: false,
    showWhatsApp: false,
    videoUrl: null,
    street: undefined,
    postcode: undefined,
    exactLatitude: null,
    exactLongitude: null,
    cadence: rentalMode === 'long' ? 'mes' : 'noche',
    monthlyPrice: rentalMode === 'long' ? 725 : null,
    nightlyPrice: rentalMode === 'holiday' ? 55 : null,
    weeklyPrice: rentalMode === 'holiday' ? 330 : null,
    availableUntil: null,
    minimumStayMonths: rentalMode === 'long' ? 1 : 0,
    minimumNights: rentalMode === 'holiday' ? 2 : null,
    depositAmount: 0,
    depositText: null,
    billsText: null,
    bathroom: 'Baño compartido',
    kitchen: 'Cocina compartida',
    furnished: true,
    shower: 'Ducha compartida',
    homeSizeM2: 80,
    bathroomCount: 2,
    rentalUnit: 'room',
    bedType: 'single',
    bedCount: 1,
    currentRoomResidents: 0,
    availableSpots: 1,
    toilet: 'Aseo compartido',
    householdGender: 'mixed',
    householdHasChildren: false,
    heatingType: 'none',
    accessible: false,
    floor: '2',
    couplesAllowed: false,
    acceptedTenantTypes: ['man', 'woman'],
    tenantRequirement: 'any',
    smokingAllowed: false,
    petsAllowed: false,
    childrenAllowed: false,
    empadronamientoAllowed: true,
    amenities: ['Wi-Fi'],
    status: 'published',
    latitude: 28.061,
    longitude: -16.733,
    homeDescription: 'Vivienda compartida.',
    advertiserName: null,
    source: null,
    priceCurrency: 'EUR',
    expiresAt: '2099-01-01T00:00:00Z',
    views: 1,
    closedReason: null,
  }
}

test('production mobile cards and detail keep photo carousel for eligible long-term rentals', async ({ page }) => {
  test.skip(test.info().project.name !== 'mobile-chromium', 'Customer regression is mobile-specific; API contract is covered by backend integration.')

  for (const rentalMode of ['long'] as const) {
    const item = card(rentalMode)
    await page.route('**/api/v1/listings/search/cards', async (route) => {
      await route.fulfill({ json: { items: [item], total: 1, nextCursor: null, previousCursor: null } })
    })
    await page.route(`**/api/v1/listings/${item.id}`, async (route) => {
      await route.fulfill({ json: detail(rentalMode) })
    })
    await page.route(`**/api/v1/listings/similar/${item.id}`, async (route) => {
      await route.fulfill({ json: [] })
    })

    await page.goto(`/#/buscar?q=Tenerife&alquiler=${rentalMode}`)
    const results = page.getByTestId('mobile-results')
    const resultCard = results.locator('.m2-result-card').first()
    await expect(resultCard).toBeVisible()
    await expect(resultCard.locator('.m2-result-card__counter')).toContainText('1/5')
    await resultCard.locator('.m2-result-card__next').click()
    await expect(resultCard.locator('.m2-result-card__counter')).toContainText('2/5')

    await resultCard.locator('.m2-result-card__image-button').click()
    await expect(page.locator('.listing-page')).toBeVisible()
    await expect(page.locator('.gallery-main > span')).toHaveText('1/5')
    await page.getByRole('button', { name: 'Foto siguiente', exact: true }).click()
    await expect(page.locator('.gallery-main > span')).toHaveText('2/5')

    await page.unroute('**/api/v1/listings/search/cards')
    await page.unroute(`**/api/v1/listings/${item.id}`)
    await page.unroute(`**/api/v1/listings/similar/${item.id}`)
  }
})


test('production mobile long-term card recovers its full internal gallery when bounded card payload is truncated', async ({ page }) => {
  test.skip(test.info().project.name !== 'mobile-chromium', 'Customer regression is mobile-specific.')

  const item = card('long')
  const truncated = { ...item, imageUrls: [gallery[0]], coverImageUrl: gallery[0] }

  await page.route('**/api/v1/listings/search/cards', async (route) => {
    await route.fulfill({ json: { items: [truncated], total: 1, nextCursor: null, previousCursor: null } })
  })
  let releaseGallery: () => void = () => undefined
  const galleryGate = new Promise<void>((resolve) => { releaseGallery = resolve })
  await page.route(`**/api/v1/listings/${item.id}/images`, async (route) => {
    // A slow legacy-gallery endpoint must not hold the entire search page.
    await galleryGate
    await route.fulfill({
      json: gallery.map((url, index) => ({
        assetId: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`,
        url,
        sortOrder: index,
        isCover: index === 0,
      })),
    })
  })

  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const resultCard = page.getByTestId('mobile-results').locator('.m2-result-card').first()
  await expect(resultCard).toBeVisible()
  await expect(resultCard.locator('.m2-result-card__counter')).toContainText('1/1')
  releaseGallery()
  await expect(resultCard.locator('.m2-result-card__counter')).toContainText('1/5')
  await resultCard.locator('.m2-result-card__next').click()
  await expect(resultCard.locator('.m2-result-card__counter')).toContainText('2/5')
})
