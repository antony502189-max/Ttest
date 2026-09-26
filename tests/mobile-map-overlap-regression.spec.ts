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

test('same-address cluster opens one full-card carousel without moving coordinates', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')
  const css = readFileSync('src/mobile-map-ideal.css', 'utf8')

  expect(layer).toContain('onClusterClick:')
  expect(layer).toContain('exactCoincidentListingIds(mappedItems, clusteredIds)')
  expect(layer).toContain('setCoincidentIds(coincidentIds)')
  expect(layer).toContain('data-group-size={carousel.length}')
  expect(layer).toContain("'m2-map-listing-card'")
  expect(layer).toContain('m2-map-listing-carousel__arrow--prev')
  expect(layer).toContain('m2-map-listing-carousel__arrow--next')
  expect(layer).not.toContain('mobile-map-coincident-option-')
  expect(css).toContain('.m2-map-listing-card.is-current')
  expect(css).toContain('.m2-map-listing-card.is-previous')
  expect(css).toContain('.m2-map-listing-card.is-next')
})

test('same-address carousel is not capped at four listings', () => {
  const overlap = readFileSync('src/lib/map-marker-overlap.ts', 'utf8')
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')

  expect(overlap).toContain('export function coincidentListingIdsFor')
  expect(layer).toContain('coincidentListingIdsFor(mappedItems, selectedId)')
  expect(layer).not.toMatch(/slice\(0,\s*4\)/)
  expect(layer).not.toMatch(/coincidentIds\.length\s*[><=]+\s*4/)
})

test('same-address carousel preserves the external source link contract on each full card', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')

  expect(layer).toContain('const externalUrl = item.isExternal && item.sourceUrl ? item.sourceUrl : null')
  expect(layer).toContain('<a className="m2-map-listing-preview__media" href={externalUrl}')
  expect(layer).toContain('<a className="m2-map-listing-preview__open" href={externalUrl}')
})

test('mobile same-address carousel exposes whole neighboring cards and glides between roles', () => {
  const layer = readFileSync('src/components/mobile-map-listings-layer.tsx', 'utf8')
  const css = readFileSync('src/mobile-map-ideal.css', 'utf8')

  expect(layer).toContain("position: 'previous'")
  expect(layer).toContain("position: 'current'")
  expect(layer).toContain("position: 'next'")
  expect(layer).toContain("carousel.length === 2")
  expect(layer).toContain("{ item: selected, position: 'current' }, { item: next!, position: 'next' }")
  expect(css).toContain('transform: translate(-146%, -50%) scale(.94)')
  expect(css).toContain('transform: translate(-50%, -50%) scale(1)')
  expect(css).toContain('transform: translate(46%, -50%) scale(.94)')
  expect(css).toContain('transition:')
  expect(css).toContain('cubic-bezier(.22, .8, .2, 1)')
  expect(css).toContain('height: 14.5rem')
  expect(css).toContain('height: 13rem')
  expect(css).toContain('grid-template-columns: 6rem minmax(0, 1fr)')
  expect(css).toContain("-webkit-line-clamp: 3")
  expect(css).toContain("min-height: 1.85rem")
  expect(layer).toContain('capacityAlreadyCovered')
  expect(css).not.toContain('.m2-map-listing-carousel .m2-map-listing-preview__media-shell.has-neighbor-peeks')
})

test('desktop same-address carousel also moves complete listing cards, not image thumbnails', () => {
  const sheet = readFileSync('src/components/map/selected-listing-sheet.tsx', 'utf8')
  const css = readFileSync('src/map.css', 'utf8')

  expect(sheet).toContain("selected-listing-carousel__card")
  expect(sheet).toContain("position: 'previous'")
  expect(sheet).toContain("position: 'current'")
  expect(sheet).toContain("position: 'next'")
  expect(sheet).toContain("carousel.length === 2")
  expect(sheet).not.toContain('selected-listing-sheet__neighbor-peek')
  expect(css).toContain('.selected-listing-carousel .selected-listing-sheet.is-current')
  expect(css).toContain('.selected-listing-carousel .selected-listing-sheet.is-previous')
  expect(css).toContain('.selected-listing-carousel .selected-listing-sheet.is-next')
  expect(css).toContain('cubic-bezier(.22, .8, .2, 1)')
  expect(css).toContain('height: 12.75rem')
  expect(css).toContain('height: 10.9rem')
  expect(css).toContain('grid-template-columns: 7.35rem minmax(0, 1fr) auto')
})
