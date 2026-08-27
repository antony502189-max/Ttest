import { expect, test, type Page } from '@playwright/test'

const listing = {
  id: 'promotion-test',
  area: 'Centro',
  price: 650,
  sourcePriceText: undefined,
  promoted: true,
}

async function seedPromotedMapListings(page: Page) {
  await page.goto('/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  const promotedPayload = await page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listings:v3')!)
    const [top, ordinary] = stored.data.filter((item: { status: string }) => item.status === 'Publicado')
    return JSON.stringify({
      version: 3,
      data: [{ ...top, promoted: true }, { ...ordinary, promoted: false }],
    })
  })
  await page.addInitScript((payload) => {
    localStorage.setItem('112233:listings:v3', payload)
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, promotedPayload)
}

test('shared map marker renders promoted listings in the TOP marker state', async ({ page }) => {
  await page.goto('/')
  const marker = await page.evaluate(async (item) => {
    const icons = await import('/src/components/map/map-icons.ts')
    return icons.createPriceMarkerContent(item as never).querySelector('.map-price-marker')?.className
  }, listing)
  expect(marker).toContain('is-promoted')
})

test('shared map marker leaves ordinary listings unchanged', async ({ page }) => {
  await page.goto('/')
  const marker = await page.evaluate(async (item) => {
    const icons = await import('/src/components/map/map-icons.ts')
    return icons.createPriceMarkerContent(item as never).querySelector('.map-price-marker')?.className
  }, { ...listing, promoted: false })
  expect(marker).not.toContain('is-promoted')
})

test('shared marker state switches TOP styling at runtime without recreation', async ({ page }) => {
  await page.goto('/')
  const classes = await page.evaluate(async (item) => {
    const icons = await import('/src/components/map/map-icons.ts')
    const content = icons.createPriceMarkerContent({ ...item, promoted: false } as never)
    icons.setPriceMarkerState(content, false, false, true)
    const promoted = content.querySelector('.map-price-marker')?.className
    icons.setPriceMarkerState(content, false, false, false)
    return { promoted, ordinary: content.querySelector('.map-price-marker')?.className }
  }, listing)

  expect(classes.promoted).toContain('is-promoted')
  expect(classes.ordinary).not.toContain('is-promoted')
})

test('mobile marker stylesheet gives TOP markers a red override', async ({ page }) => {
  await page.goto('/')
  const css = await page.evaluate(async () => (await import('/src/mobile-map-ideal.css?raw')).default)
  expect(css).toContain('.m2-listing-marker .map-price-marker.is-promoted')
  expect(css).toContain('background: #d92d20')
})

test('desktop map mounts a red high-priority TOP marker and keeps it red when selected', async ({ page }) => {
  await seedPromotedMapListings(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/?top-promotion=desktop#/buscar?q=Tenerife&vista=mapa')

  const topMarker = page.locator('.idealista-map-view .map-price-marker.is-promoted').first()
  const topShell = topMarker.locator('..')
  await expect(topMarker).toBeVisible()
  await expect(topShell).toHaveAttribute('data-marker-z-index', '100')
  expect(await topMarker.evaluate((node) => getComputedStyle(node).backgroundColor)).toBe('rgb(217, 45, 32)')

  await topMarker.click()
  await expect(topMarker).toHaveClass(/is-selected/)
  await expect(topShell).toHaveAttribute('data-marker-z-index', '3000')
  expect(await topMarker.evaluate((node) => getComputedStyle(node).backgroundColor)).toBe('rgb(180, 35, 24)')
})

test('mobile map mounts a red high-priority TOP marker at every supported width', async ({ page }) => {
  await seedPromotedMapListings(page)
  for (const [width, height] of [[320, 700], [360, 800], [390, 844], [430, 932]] as const) {
    await page.setViewportSize({ width, height })
    await page.goto(`/?top-promotion=mobile-${width}#/buscar?q=Tenerife&vista=mapa`)

    const topMarker = page.locator('.m2-listing-marker .map-price-marker.is-promoted').first()
    const topShell = topMarker.locator('..')
    await expect(topMarker).toBeVisible()
    await expect(topShell).toHaveAttribute('data-marker-z-index', '100')
    expect(await topMarker.evaluate((node) => getComputedStyle(node).backgroundColor)).toBe('rgb(217, 45, 32)')

    await topMarker.click()
    await expect(topMarker).toHaveClass(/is-selected/)
    await expect(topShell).toHaveAttribute('data-marker-z-index', '4000')
    expect(await topMarker.evaluate((node) => getComputedStyle(node).backgroundColor)).toBe('rgb(180, 35, 24)')
  }
})
