import { expect, test } from '@playwright/test'

async function mappedListings(page: import('@playwright/test').Page) {
  return page.evaluate(async () => {
    const { toListing, toCardListing } = await import('/src/api/listings.ts')
    const dto = {
      id: 'external-unknown-availability', title: 'Estudio en Ador', city: 'Ador', area: 'Ador',
      approximateAddress: 'Ador', price: 700, monthlyPrice: 700, rentalMode: 'long', cadence: 'mes',
      roomType: 'Estudio', availableFrom: null, publishedAt: '2026-10-08',
      imageUrls: [], amenities: [], restrictions: [], currentResidents: 0, bedroomCount: 0,
      owner: { name: '', initials: '', since: null, response: '', verified: false },
      status: 'published', isExternal: true, primarySource: 'Pisos',
      sourceUrl: 'https://www.pisos.com/alquilar/piso-ador_centro_urbano-67526936751_534221/',
    }
    return [toListing, toCardListing].map((map) => ({
      unknown: map(dto),
      known: map({ ...dto, availableFrom: '2026-12-15' }),
      native: map({ ...dto, isExternal: false, availableFrom: '2026-11-01' }),
      nativeFallback: map({ ...dto, isExternal: false }),
    }))
  })
}

test('detail and card adapters preserve unknown external availability and real supplied dates', async ({ page }) => {
  await page.goto('/')
  const rows = await mappedListings(page)
  for (const row of rows) {
    expect(row.unknown.availableFrom).toBe('')
    expect(row.unknown.available).toBe('Consultar disponibilidad')
    expect(row.known.availableFrom).toBe('2026-12-15')
    expect(row.native.availableFrom).toBe('2026-11-01')
    expect(row.nativeFallback.availableFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  }
})

for (const width of [390, 1440]) {
  test(`external result with no source date shows availability to consult at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 960 })
    await page.goto('/')
    const [mapped] = await mappedListings(page)
    await page.evaluate((listing) => {
      localStorage.setItem('112233:listings:v3', JSON.stringify({
        version: 3, data: [{ ...listing, city: 'Adeje', area: 'Adeje', approximateAddress: 'Adeje' }],
      }))
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    }, mapped.unknown)
    await page.goto('/#/buscar?q=Adeje&alquiler=long')
    await page.reload()
    const card = page.locator(`[data-listing-id="${mapped.unknown.id}"]`).first()
    await expect(card).toBeVisible()
    await expect(card).toContainText('Consultar disponibilidad')
    await expect(card).not.toContainText('Disponible desde')
  })
}
