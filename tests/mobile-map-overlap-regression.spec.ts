import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
}

test('mobile map keeps coincident listings at one truthful position for clustering', async ({ page }) => {
  await page.goto('/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  const ids = await page.evaluate(() => {
    const key = '112233:listings:v3'
    const payload = JSON.parse(localStorage.getItem(key)!)
    const pair = payload.data.slice(0, 2)
    pair.forEach((listing: any) => {
      listing.coordinates = { lat: 28.1299668, lng: -16.7578612 }
      listing.city = 'Adeje'
      listing.area = 'Arme?ime'
      listing.rentalMode = 'long'
      listing.status = 'Publicado'
    })
    localStorage.setItem(key, JSON.stringify(payload))
    return pair.map((listing: any) => listing.id) as string[]
  })
  await page.reload()
  await finishOnboarding(page)
  await page.locator('.m2-select-row').click()
  await page.getByTestId('search-map').click()
  await expect(page.getByTestId('google-map')).toBeVisible()

  const markers = ids.map((id) => page.getByTestId(`mobile-map-marker-${id}`))
  for (const marker of markers) await expect(marker).toHaveAttribute('data-coincident-count', '2')
  const positions = await Promise.all(markers.map((marker) => marker.getAttribute('data-display-position')))
  expect(new Set(positions).size).toBe(1)
  for (const position of positions) expect(position).toBe('28.1299668,-16.7578612')
})


test('same-address cluster opens one listing carousel without moving coordinates', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')
  const css = readFileSync('src/mobile-map-ideal.css', 'utf8')

  expect(layer).toContain('onClusterClick:')
  expect(layer).toContain('exactCoincidentListingIds(mappedItems, clusteredIds)')
  expect(layer).toContain('setCoincidentIds(coincidentIds)')
  expect(layer).toContain('data-group-size={carousel.length}')
  expect(layer).toContain('m2-map-listing-preview__carousel-arrow--prev')
  expect(layer).toContain('m2-map-listing-preview__carousel-arrow--next')
  expect(layer).not.toContain('mobile-map-coincident-option-')
  expect(css).toContain('.m2-map-listing-preview__carousel-arrow')
  expect(css).toContain('.m2-map-listing-preview__carousel-count')
})


test('same-address carousel is not capped at four listings', () => {
  const overlap = readFileSync('src/lib/map-marker-overlap.ts', 'utf8')
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')

  expect(overlap).toContain('export function coincidentListingIdsFor')
  expect(layer).toContain('coincidentListingIdsFor(mappedItems, selectedId)')
  expect(layer).not.toMatch(/slice\(0,\s*4\)/)
  expect(layer).not.toMatch(/coincidentIds\.length\s*[><=]+\s*4/)
})

test('same-address carousel preserves the external source image-link contract', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')

  expect(layer).toContain("cn('m2-map-listing-preview__media-shell', carousel.length > 1 && 'has-neighbor-peeks')")
  expect(layer).toContain('<a className="m2-map-listing-preview__media" href={externalUrl}')
})

test('same-address carousel exposes neighboring listing peeks and wraps in both directions', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')
  const css = readFileSync('src/mobile-map-ideal.css', 'utf8')

  expect(layer).toContain('mobile-map-listing-peek-prev')
  expect(layer).toContain('mobile-map-listing-peek-next')
  expect(layer).toContain('(carouselIndex - 1 + carousel.length) % carousel.length')
  expect(layer).toContain('(carouselIndex + 1) % carousel.length')
  expect(css).toContain('.m2-map-listing-preview__neighbor-peek--prev')
  expect(css).toContain('.m2-map-listing-preview__neighbor-peek--next')
  expect(css).toContain('width: 72%')
})


test('desktop same-address carousel exposes neighboring peeks and wraps in both directions', () => {
  const sheet = readFileSync('src/components/map/selected-listing-sheet.tsx', 'utf8')
  const css = readFileSync('src/map.css', 'utf8')

  expect(sheet).toContain('selected-listing-sheet__neighbor-peek--prev')
  expect(sheet).toContain('selected-listing-sheet__neighbor-peek--next')
  expect(sheet).toContain('(carouselIndex - 1 + carousel.length) % carousel.length')
  expect(sheet).toContain('(carouselIndex + 1) % carousel.length')
  expect(css).toContain('.selected-listing-sheet__neighbor-peek--prev')
  expect(css).toContain('.selected-listing-sheet__neighbor-peek--next')
  expect(css).toContain('.selected-listing-sheet__media.has-neighbor-peeks .selected-listing-sheet__primary-photo')
  expect(css).toContain('width: 72%')
})
