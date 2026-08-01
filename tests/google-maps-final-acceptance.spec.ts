import { expect, test, type Page } from '@playwright/test'

const mapReady = async (page: Page) => {
  await expect(page.locator('.google-map-canvas')).toHaveAttribute('data-map-instance', 'google-ready', { timeout: 20_000 })
  await expect.poll(() => page.locator('.map-price-marker-shell, .map-cluster-marker-shell').count(), { timeout: 20_000 }).toBeGreaterThan(0)
}

const firstVisible = async (page: Page, selector: string) => {
  const locator = page.locator(selector)
  const index = await locator.evaluateAll((nodes) => nodes.findIndex((node) => {
    const box = node.getBoundingClientRect()
    return box.width > 0 && box.height > 0 && box.left < innerWidth && box.right > 0 && box.top < innerHeight && box.bottom > 0
  }))
  expect(index, `Expected a visible ${selector}`).toBeGreaterThanOrEqual(0)
  return locator.nth(index)
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
})

test('selected Advanced Marker has priority, opens the sheet, and programmatic selection stays clean', async ({ page }) => {
  await page.goto('/#/buscar?q=Adeje&alquiler=long&vista=mapa')
  await mapReady(page)
  await (await firstVisible(page, '.map-price-marker-shell')).click()
  const selected = page.locator('.map-price-marker-shell:has(.is-selected)')
  await expect(selected).toHaveAttribute('data-marker-z-index', '3000')
  await expect(page.locator('.selected-listing-sheet')).toBeVisible()
  await expect(page.getByRole('button', { name: /buscar en esta zona/i })).toHaveCount(0)
  const sheet = await page.locator('.selected-listing-sheet').boundingBox()
  expect(sheet).not.toBeNull()
  expect(sheet!.y).toBeGreaterThanOrEqual(0)
  expect(sheet!.y + sheet!.height).toBeLessThanOrEqual(768)
})

test('manual pan exposes Search this area while a result refit does not', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await mapReady(page)
  const searchArea = page.getByRole('button', { name: /buscar en esta zona/i })
  await expect(searchArea).toHaveCount(0)
  const canvas = page.locator('.google-map-canvas')
  await canvas.hover()
  await page.mouse.wheel(0, -600)
  await expect(searchArea).toBeVisible({ timeout: 10_000 })
  await searchArea.click()
  await expect(searchArea).toHaveCount(0)
})

test('map/list, multiple canonical zones, and polygon restore from URL and reload', async ({ page }) => {
  const polygon = '28.08,-16.79;28.18,-16.79;28.18,-16.62;28.08,-16.62'
  await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&zonas=municipality%3Aadeje%2Cmunicipality%3Aarona`)
  await mapReady(page)
  await expect(page).toHaveURL(/vista=mapa/)
  await page.reload()
  await expect(page.getByRole('radio', { name: /mostrar habitaciones en el mapa/i })).toBeChecked()
  await expect(page).toHaveURL(/municipality%3Aadeje%2Cmunicipality%3Aarona/)
  await page.getByRole('radio', { name: /mostrar lista/i }).click()
  await expect(page).not.toHaveURL(/vista=mapa/)
  await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&poligono=${encodeURIComponent(polygon)}`)
  await mapReady(page)
  await expect(page.getByRole('button', { name: /eliminar zona/i })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: /eliminar zona/i })).toBeVisible()
  await expect(page).toHaveURL(/poligono=/)
})

test('official district hierarchy selects a stable ID and restores it from URL', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await page.getByRole('button', { name: /abrir selección de ubicación/i }).click()
  await page.getByRole('button', { name: /seleccionar zonas en el mapa/i }).click()
  await expect(page.getByRole('region', { name: /seleccionar zonas de tenerife/i })).toBeVisible()
  await page.getByRole('button', { name: /ver zonas dentro de santa cruz de tenerife/i }).click()
  await page.getByRole('button', { name: /centro-ifara distrito/i }).click()
  await page.getByRole('button', { name: /ver \d+ habitaciones/i }).click()
  await expect(page).toHaveURL(/district%3Asanta-cruz-de-tenerife%3Acentro-ifara/)
  await page.reload()
  await expect(page).toHaveURL(/district%3Asanta-cruz-de-tenerife%3Acentro-ifara/)
  await page.getByRole('button', { name: /abrir selección de ubicación/i }).click()
  await page.getByRole('button', { name: /seleccionar zonas en el mapa/i }).click()
  await page.getByLabel(/buscar municipio, distrito o barrio/i).fill('CENTRO-IFARA')
  await expect(page.getByRole('button', { name: /centro-ifara distrito/i })).toHaveAttribute('aria-pressed', 'true')
})

test('map auth errors keep a usable fallback', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await mapReady(page)
  await page.evaluate(() => window.dispatchEvent(new Event('112233:google-maps-auth-failure')))
  await expect(page.locator('.map-inline-error')).toContainText(/dominio|referrer/i)
  await expect(page.locator('.map-list-alternative')).toBeVisible()
  await expect(page.locator('.map-list-alternative button')).not.toHaveCount(0)
})
