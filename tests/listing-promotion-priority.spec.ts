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

for (const width of [320, 390] as const) {
  test(`mobile TOP listing has a visible non-interactive thumb at upper-left: ${width}px`, async ({ page }) => {
    const { promotedId, ordinaryId } = await seedStickyPromotion(page)
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/?sticky-promotion=1#/buscar?q=Tenerife&alquiler=long')

    const cards = page.locator('.m2-result-card')
    await expect(cards).toHaveCount(2)
    await expect(cards.first()).toHaveAttribute('data-listing-id', promotedId)
    await expect(cards.nth(1)).toHaveAttribute('data-listing-id', ordinaryId)
    const topThumb = cards.first().getByTestId('listing-top-thumb')
    await expect(topThumb).toHaveText('👍')
    await expect(topThumb).toHaveAttribute('aria-label', 'Anuncio TOP')
    await expect(topThumb).toBeVisible()
    await expect(cards.nth(1).getByTestId('listing-top-thumb')).toHaveCount(0)
    const box = await topThumb.boundingBox()
    const media = await cards.first().locator('.m2-result-card__media').boundingBox()
    expect(box).not.toBeNull()
    expect(media).not.toBeNull()
    expect(box!.x - media!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x - media!.x).toBeLessThanOrEqual(24)
    expect(box!.y - media!.y).toBeGreaterThanOrEqual(0)
    expect(box!.y - media!.y).toBeLessThanOrEqual(24)
    expect(await topThumb.evaluate(node => getComputedStyle(node).pointerEvents)).toBe('none')
  })
}

test('desktop TOP listing uses the same thumb without changing ordinary cards', async ({ page }) => {
  const { promotedId, ordinaryId } = await seedStickyPromotion(page)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/?sticky-promotion=1#/buscar?q=Tenerife&alquiler=long')
  const cards = page.locator('.results-list .property-card')
  await expect(cards).toHaveCount(2)
  await expect(cards.first()).toHaveAttribute('data-listing-id', promotedId)
  await expect(cards.nth(1)).toHaveAttribute('data-listing-id', ordinaryId)
  await expect(cards.first().getByTestId('listing-top-thumb')).toHaveText('👍')
  await expect(cards.nth(1).getByTestId('listing-top-thumb')).toHaveCount(0)
})


test('stable production guard keeps TOP above a newly inserted ordinary listing', async ({ page }) => {
  await page.goto('/')
  const ids = await page.evaluate(async () => {
    const { prioritizePromotedListings } = await import('/src/lib/search.ts')
    const top = { id: 'top', promoted: true }
    const newlyPublished = { id: 'new', promoted: false }
    return prioritizePromotedListings([newlyPublished, top] as never).map((listing) => listing.id)
  })

  expect(ids).toEqual(['top', 'new'])
})

test('mobile focus never lifts a normal listing above an active TOP', async ({ page }) => {
  const { promotedId, ordinaryId } = await seedStickyPromotion(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/?sticky-promotion=1#/buscar?q=Tenerife&alquiler=long&anuncio=${ordinaryId}`)

  const cards = page.locator('.m2-result-card')
  await expect(cards).toHaveCount(2)
  await expect(cards.first()).toHaveAttribute('data-listing-id', promotedId)
  await expect(cards.nth(1)).toHaveAttribute('data-listing-id', ordinaryId)
})
