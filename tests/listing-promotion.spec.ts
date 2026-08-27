import { expect, test } from '@playwright/test'

const listing = {
  id: 'promotion-test',
  area: 'Centro',
  price: 650,
  sourcePriceText: undefined,
  promoted: true,
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
