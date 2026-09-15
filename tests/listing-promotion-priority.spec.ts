import { expect, test, type Page } from '@playwright/test'

async function seedStickyPromotion(page: Page) {
  await page.goto('/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  const seeded = await page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listings:v3')!)
    const published = stored.data.filter((item: { status: string; rentalMode: string }) => item.status === 'Publicado' && item.rentalMode === 'long')
    const promoted = { ...published[0], promoted: true, publishedAt: '2025-01-01', price: 999, monthlyPrice: 999 }
    const ordinary = { ...published[1], promoted: false, publishedAt: '2099-01-01', price: 1, monthlyPrice: 1 }
    return {
      promotedId: promoted.id,
      ordinaryId: ordinary.id,
      payload: JSON.stringify({ version: 3, data: [promoted, ordinary] }),
    }
  })
  await page.addInitScript(({ payload }) => {
    localStorage.setItem('112233:listings:v3', payload)
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, seeded)
  return seeded
}

test('client sort keeps the promoted tier ahead of newer and cheaper ordinary listings', async ({ page }) => {
  await page.goto('/')
  const results = await page.evaluate(async () => {
    const { sortListings } = await import('/src/lib/search.ts')
    const promoted = { id: 'promoted', promoted: true, publishedAt: '2025-01-01', rentalMode: 'long', price: 999, monthlyPrice: 999 }
    const ordinary = { id: 'ordinary', promoted: false, publishedAt: '2099-01-01', rentalMode: 'long', price: 1, monthlyPrice: 1 }
    return ['Más recientes', 'Más antiguos', 'Precio más bajo', 'Precio más alto', 'Relevancia'].map((sort) =>
      sortListings([ordinary, promoted] as never, sort).map((listing) => listing.id),
    )
  })

  for (const ids of results) expect(ids[0]).toBe('promoted')
})

test('mobile results keep a promoted listing first without showing a TOP badge', async ({ page }) => {
  const { promotedId, ordinaryId } = await seedStickyPromotion(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?sticky-promotion=1#/buscar?q=Tenerife&alquiler=long')

  const cards = page.locator('.m2-result-card')
  await expect(cards).toHaveCount(2)
  await expect(cards.first()).toHaveAttribute('data-listing-id', promotedId)
  await expect(cards.nth(1)).toHaveAttribute('data-listing-id', ordinaryId)
  await expect(page.locator('.m2-result-card__top')).toHaveCount(0)
})
