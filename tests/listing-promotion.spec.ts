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
