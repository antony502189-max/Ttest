import { expect, test, type Page } from '@playwright/test'
import { isExpectedHeadlessVectorFallback } from './helpers/google-maps-console'

async function settle(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('P0 current mobile home preserves the locked APK hierarchy and links all four tabs', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await settle(page)
  await expect(page.locator('.m2-home')).toBeVisible()
  await expect(page.locator('.m2-mode-switch button')).toHaveCount(2)
  await expect(page.locator('.m2-occupant-trigger')).toBeVisible()
  await expect(page.locator('.m2-select-row')).toBeVisible()
  await expect(page.getByTestId('open-location')).toBeVisible()
  await expect(page.locator('.m2-bottom-nav button')).toHaveCount(4)
  await expect(page.getByRole('button', { name: 'Chat', exact: true })).toHaveCount(0)

  for (const [label, route] of [['Búsquedas', 'busquedas-guardadas'], ['Favoritos', 'favoritos'], ['Menú', 'menu']] as const) {
    await page.getByRole('button', { name: label, exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`#/${route}`))
  }

  await page.goto('/#/mensajes')
  await expect(page).toHaveURL(/#\/$/)
  await expect(page.locator('.m2-home')).toBeVisible()
})

test('P1 desktop multiple municipalities stay synchronized with URL, filters and reload', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  await settle(page)
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar zonas en el mapa' }).click()
  const browser = page.getByRole('region', { name: 'Seleccionar zonas de Tenerife' })
  await browser.getByRole('button', { name: /^Adeje\b/ }).click()
  await browser.getByRole('button', { name: /^Arona\b/ }).click()
  await expect(page.getByText('2 zonas seleccionadas', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^Ver \d+ habitaciones$/ }).click()
  await expect.poll(() => decodeURIComponent(page.url())).toContain('zonas=municipality:adeje,municipality:arona')
  await expect(page.locator('.filter-count')).toHaveText(['1', '1'])
  await page.reload()
  await expect.poll(() => decodeURIComponent(page.url())).toContain('zonas=municipality:adeje,municipality:arona')
})

test('P1 municipality list remains usable when detailed GeoJSON cannot load', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 844 })
  await page.goto('/#/buscar?q=Tenerife')
  await page.route('**/tenerife-zone-hierarchy.geojson*', (route) => route.abort())
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar zonas en el mapa' }).click()
  await expect(page.getByRole('status').filter({ hasText: /límites detallados/i })).toBeVisible()
  const adeje = page.getByRole('region', { name: 'Seleccionar zonas de Tenerife' }).getByRole('button', { name: /^Adeje\b/ })
  await adeje.click()
  await expect(adeje).toHaveAttribute('aria-pressed', 'true')
})

test('P0 mobile and desktop maps retain their intended separate implementations', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.locator('.m2-map-canvas')).toBeVisible()
  await expect(page.locator('.google-map-canvas')).toHaveCount(0)
  await page.getByRole('button', { name: 'Lista' }).click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()

  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  const map = page.locator('.google-map-canvas')
  await expect(map).toHaveAttribute('data-map-instance', 'google-ready', { timeout: 20_000 })
  await expect(map).toHaveAttribute('data-map-center', /.+/)
  await expect(page.locator('.map-results-split')).toBeVisible()
  const center = await map.getAttribute('data-map-center')
  await page.locator('.map-results-cards .property-card').first().getByRole('link').first().focus()
  await expect(page.locator('.price-marker.is-highlighted, .room-cluster.is-highlighted')).toHaveCount(1)
  await expect(map).toHaveAttribute('data-map-center', center ?? '')
})

test('P1 core routes have no horizontal overflow or unexpected console errors across the responsive matrix', async ({ page }) => {
  test.setTimeout(240_000)
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !isExpectedHeadlessVectorFallback(message.text())) consoleErrors.push(message.text())
  })

  for (const width of [360, 390, 430, 768, 1024, 1280, 1440]) {
    const height = width < 768 ? 844 : 900
    await page.setViewportSize({ width, height })
    for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa']) {
      await page.goto(route)
      await settle(page)
      const mapSelector = width < 768 ? '.m2-map-canvas' : '.google-map-canvas'
      if (route.includes('vista=mapa')) await expect(page.locator(mapSelector)).toBeVisible()
      const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth)
      expect(overflow, `${route} at ${width}px`).toBeLessThanOrEqual(1)
    }
  }
  expect(consoleErrors).toEqual([])
})
