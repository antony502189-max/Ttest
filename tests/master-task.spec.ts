import { expect, test, type Page } from '@playwright/test'

async function clickFirstInViewport(page: Page, selector: string) {
  const elements = page.locator(selector)
  const index = await elements.evaluateAll((nodes) => nodes.findIndex((node) => {
    const rect = node.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight
  }))
  expect(index, `No visible ${selector}`).toBeGreaterThanOrEqual(0)
  await elements.nth(index).click()
}

async function hasInViewport(page: Page, selector: string) {
  return page.locator(selector).evaluateAll((nodes) => nodes.some((node) => {
    const rect = node.getBoundingClientRect()
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight
  }))
}

async function settle(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
}

test('P0 home follows the mobile-first room-only hierarchy', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await settle(page)
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
  await expect(page.getByText(/Larga estancia y turística/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /Encontrar habitación/i })).toBeVisible()
  await expect(page.locator('#move-date')).toHaveCount(0)
  await expect(page.getByText('Anuncios verificados', { exact: true })).toBeVisible()
  await expect(page.getByText('Guarda tus favoritos', { exact: true })).toBeVisible()
  await expect(page.getByText('Contacta sin comisión', { exact: true })).toBeVisible()
  await expect(page.locator('.bottom-nav a')).toHaveCount(5)
})

test('P1 multiple municipalities stay synchronized with URL and filters', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  await settle(page)
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar municipios en el mapa' }).click()
  const group = page.getByRole('group', { name: 'Municipios de Tenerife' })
  await expect(group).toBeVisible()
  await group.getByRole('button', { name: /^Adeje\b/ }).click()
  await group.getByRole('button', { name: /^Arona\b/ }).click()
  await expect(page.getByText('2 zonas seleccionadas', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^Ver \d+ habitaciones$/ }).click()
  await expect.poll(() => decodeURIComponent(page.url())).toContain('zonas=adeje,arona')
  await expect(page.locator('.filter-count')).toHaveText(['1', '1'])
  const locations = page.locator('.results-list .property-location')
  const locationCount = await locations.count()
  expect(locationCount).toBeGreaterThan(0)
  await expect(locations.filter({ hasText: /Adeje|Arona/ })).toHaveCount(locationCount)
  await page.reload()
  await settle(page)
  await expect.poll(() => decodeURIComponent(page.url())).toContain('zonas=adeje,arona')
})

test('P1 municipality list remains usable when GeoJSON cannot load', async ({ page }) => {
  await page.route('**/tenerife-municipalities.geojson*', (route) => route.abort())
  await page.goto('/#/buscar?q=Tenerife')
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar municipios en el mapa' }).click()
  await expect(page.getByRole('alert').filter({ hasText: /límites municipales/i })).toBeVisible()
  const adeje = page.getByRole('group', { name: 'Municipios de Tenerife' }).getByRole('button', { name: /^Adeje\b/ })
  await adeje.click()
  await expect(adeje).toHaveAttribute('aria-pressed', 'true')
})

test('P1 municipality selector geometry stays inside a 390px viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar municipios en el mapa' }).click()
  await expect(page.locator('.zone-selection .map-layer-switcher')).toBeVisible()
  const geometry = await page.locator('.location-selector-dialog, .location-zones-panel, .zone-selection, .zone-selection__map-wrap, .zone-selection__sidebar, .zone-selection__footer').evaluateAll((nodes) => nodes.map((node) => {
    const rect = node.getBoundingClientRect()
    return { className: node.className, top: rect.top, bottom: rect.bottom, height: rect.height, display: getComputedStyle(node).display, overflow: getComputedStyle(node).overflow }
  }))
  expect(geometry, JSON.stringify(geometry, null, 2)).toHaveLength(6)
  const footer = page.locator('.zone-selection__footer')
  await expect(footer).toBeVisible()
  const box = await footer.boundingBox()
  expect(box?.y ?? 9999, JSON.stringify(geometry, null, 2)).toBeLessThan(844)
  const zoneBox = await page.locator('.zone-selection').boundingBox()
  expect(zoneBox?.width ?? 9999, JSON.stringify(geometry, null, 2)).toBeLessThanOrEqual(390)
})

test('P0 results map keeps selection, preview and manual bounds search', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Adeje&vista=mapa')
  await expect(page.locator('.google-map-canvas')).toBeVisible()
  await expect(page.getByRole('button', { name: /Buscar en esta zona/i })).toHaveCount(0)
  await expect.poll(() => hasInViewport(page, '.price-marker-shell')).toBe(true)
  await clickFirstInViewport(page, '.price-marker-shell')
  await expect(page.locator('.map-selected-card')).toBeVisible()
  await expect(page.locator('.price-marker.is-selected')).toHaveCount(1)
  await page.getByRole('button', { name: 'Lista', exact: false }).last().click()
  await expect(page).not.toHaveURL(/vista=mapa/)
  await page.getByRole('button', { name: /^Mapa/ }).last().click()
  await expect(page.locator('.map-selected-card')).toBeVisible()
  const remountedMap = page.locator('.google-map-canvas')
  await expect(remountedMap).toHaveAttribute('data-map-instance', 'google-ready')
  await expect(remountedMap).toHaveAttribute('data-map-center', /.+/)
  await remountedMap.hover()
  await page.mouse.wheel(0, -600)
  await expect(page.getByRole('button', { name: /Buscar en esta zona/i })).toBeVisible()
  await page.getByRole('button', { name: /Buscar en esta zona/i }).click()
  await expect(page.getByRole('button', { name: /Buscar en esta zona/i })).toHaveCount(0)
})

test('P0 desktop split view synchronizes cards and visible clusters without moving the map', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toBeVisible()
  await expect(map).toHaveAttribute('data-map-center', /.+/)
  const before = await map.getAttribute('data-map-center')
  const firstCardLink = page.locator('.map-results-cards .property-card').first().getByRole('link').first()
  await firstCardLink.focus()
  await expect(page.locator('.price-marker.is-highlighted, .room-cluster.is-highlighted')).toHaveCount(1)
  await expect(map).toHaveAttribute('data-map-center', before ?? '')
})

test('P1 core routes have no horizontal overflow or console errors across the responsive matrix', async ({ page }) => {
  test.setTimeout(240_000)
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  for (const width of [360, 390, 430, 768, 1024, 1280, 1440]) {
    const height = width < 768 ? 844 : 900
    await page.setViewportSize({ width, height })
    for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa']) {
      await page.goto(route)
      await settle(page)
      if (route.includes('vista=mapa')) await expect(page.locator('.google-map-canvas')).toBeVisible()
      const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth)
      expect(overflow, `${route} at ${width}px`).toBeLessThanOrEqual(1)
    }
  }
  expect(consoleErrors).toEqual([])
})
