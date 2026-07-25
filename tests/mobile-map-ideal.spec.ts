import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

async function openMap(page: Page, kind: 'search' | 'draw') {
  await page.locator('.m2-select-row').click()
  const locationAction = page.getByTestId(kind === 'search' ? 'search-map' : 'draw-zone')
  await expect(locationAction).toBeVisible()
  await locationAction.click()
  const map = page.getByTestId('google-map')
  await expect(map).toBeVisible()
  await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  return map
}

async function revealVisibleListingMarker(page: Page) {
  const visibleMarker = page.locator('.m2-listing-marker:visible').first()
  for (let attempt = 0; attempt < 5; attempt += 1) {
    if (await visibleMarker.isVisible().catch(() => false)) return visibleMarker
    const cluster = page.locator('.map-cluster-marker:visible').first()
    await expect(cluster).toBeVisible({ timeout: 20_000 })
    await cluster.click()
    await page.waitForTimeout(350)
  }
  await expect(visibleMarker).toBeVisible({ timeout: 10_000 })
  return visibleMarker
}

test('map is freely zoomable before explicit drawing activation', async ({ page }) => {
  await finishOnboarding(page)
  const map = await openMap(page, 'draw')
  await expect(page.getByTestId('freehand-overlay')).toHaveCount(0)
  const draw = page.getByRole('button', { name: 'Dibujar tu zona' })
  await expect(draw).toHaveAttribute('aria-pressed', 'false')
  const zoomBefore = await map.getAttribute('data-map-zoom')
  await map.hover()
  await page.mouse.wheel(0, -700)
  await expect.poll(async () => map.getAttribute('data-map-zoom')).not.toBe(zoomBefore)
  await draw.click()
  await expect(page.getByTestId('freehand-overlay')).toBeVisible()
  await expect(map).toHaveAttribute('data-map-interaction', 'drawing')
  await expect(page.getByRole('button', { name: 'Cancelar dibujo' })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Cancelar dibujo' }).click()
  await expect(page.getByTestId('freehand-overlay')).toHaveCount(0)
  await expect(map).toHaveAttribute('data-map-interaction', 'interactive')
})

test('published listings are visible on the map and open the matching result', async ({ page }) => {
  await finishOnboarding(page)
  const map = await openMap(page, 'search')
  await expect(map).toHaveAttribute('data-map-interaction', 'interactive')

  const visibleMarkerOrCluster = page.locator('.m2-listing-marker:visible, .map-cluster-marker:visible').first()
  await expect(visibleMarkerOrCluster).toBeVisible({ timeout: 20_000 })
  const marker = page.locator('.m2-listing-marker').first()
  await expect(marker).toBeAttached()
  await marker.evaluate((element) => element.dispatchEvent(new MouseEvent('click', { bubbles: true })))

  const preview = page.getByTestId('mobile-map-listing-preview')
  await expect(preview).toBeVisible()
  const listingId = await preview.getAttribute('data-listing-id')
  expect(listingId).toBeTruthy()
  await expect(preview.locator('.m2-map-listing-preview__requirements span')).not.toHaveCount(0)
  await preview.locator('.m2-map-listing-preview__open').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.locator('.m2-result-card').first()).toHaveAttribute('data-listing-id', listingId!)
})

test('listing requirements are visually prominent in results', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Vivienda', exact: true }).click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  const badges = results.locator('.m2-result-card').first().locator('.m2-result-card__badges span')
  await expect(badges).not.toHaveCount(0)
  await expect(badges.filter({ hasText: /Habitación para/ })).toHaveCount(1)
  const style = await badges.first().evaluate((element) => {
    const computed = getComputedStyle(element)
    return { fontWeight: Number(computed.fontWeight), height: element.getBoundingClientRect().height, border: computed.borderTopWidth }
  })
  expect(style.fontWeight).toBeGreaterThanOrEqual(700)
  expect(style.height).toBeGreaterThanOrEqual(28)
  expect(style.border).not.toBe('0px')
})
