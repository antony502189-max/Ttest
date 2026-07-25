import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.locator('.m2-home')).toBeVisible()
}

async function openSearchMap(page: Page) {
  await page.locator('.m2-select-row').click()
  await page.getByTestId('search-map').click()
  const map = page.getByTestId('google-map')
  await expect(map).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  return map
}

test('home rental mode is the same mode shown by map markers', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Turismo', exact: true }).click()
  await openSearchMap(page)
  const markers = page.locator('.m2-listing-marker')
  await expect(markers.first()).toBeAttached({ timeout: 20_000 })
  const modes = await markers.evaluateAll((nodes) => nodes.map((node) => (node as HTMLElement).dataset.rentalMode))
  expect(modes.length).toBeGreaterThan(0)
  expect(new Set(modes)).toEqual(new Set(['holiday']))
})

test('location query limits both the map and its markers', async ({ page }) => {
  await finishOnboarding(page)
  await page.locator('.m2-select-row').click()
  const input = page.getByRole('searchbox', { name: 'Municipio, zona o dirección' })
  await input.fill('Santa Cruz de Tenerife')
  await input.press('Enter')
  await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  const markers = page.locator('.m2-listing-marker')
  await expect(markers.first()).toBeAttached({ timeout: 20_000 })
  const cities = await markers.evaluateAll((nodes) => nodes.map((node) => (node as HTMLElement).dataset.city))
  expect(cities.length).toBeGreaterThan(0)
  expect(new Set(cities)).toEqual(new Set(['Santa Cruz de Tenerife']))
})

test('mobile result filters remain active after switching to the map', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByRole('button', { name: 'Vivienda', exact: true }).click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await results.getByRole('button', { name: 'Filtros', exact: true }).click()
  await page.getByLabel('Precio Máx').fill('450')
  await page.getByRole('button', { name: /Ver anuncios/ }).click()
  await page.getByRole('button', { name: 'Mapa', exact: true }).click()
  await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  const markers = page.locator('.m2-listing-marker')
  await expect(markers.first()).toBeAttached({ timeout: 20_000 })
  const prices = await markers.evaluateAll((nodes) => nodes.map((node) => Number((node as HTMLElement).dataset.price)))
  expect(prices.length).toBeGreaterThan(0)
  expect(prices.every((price) => price <= 450)).toBeTruthy()
})

test('map toolbar opens the real filters and list panels', async ({ page }) => {
  await finishOnboarding(page)
  await openSearchMap(page)
  await page.locator('.m2-map-toolbar').getByRole('button', { name: 'Filtros' }).click()
  await expect(page.locator('.m2-results-filter')).toBeVisible()
  await page.locator('.m2-results-panel header').getByRole('button', { name: 'Cerrar' }).click()
  await page.locator('.m2-results__header').getByRole('button', { name: 'Volver' }).click()
  await page.locator('.m2-map-toolbar').getByRole('button', { name: 'Listado' }).click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.locator('.m2-results__list .m2-result-card').first()).toBeVisible()
})

test('search visible area and save search are connected to real state', async ({ page }) => {
  await finishOnboarding(page)
  const map = await openSearchMap(page)
  const save = page.getByRole('button', { name: 'Guardar', exact: true })
  await save.click()
  await expect(page.getByRole('button', { name: 'Guardado', exact: true })).toBeVisible()
  await expect.poll(async () => page.evaluate(() => localStorage.getItem('112233:saved-searches:v3') ?? '')).toContain('Tenerife')

  await map.hover()
  await page.mouse.wheel(0, -500)
  const searchArea = page.getByTestId('mobile-map-search-area')
  await expect(searchArea).toBeVisible()
  await searchArea.click()
  await expect(map).toHaveAttribute('data-bounds-filtered', 'true')
  await expect(page.getByTestId('mobile-map-count')).toContainText(/\d+/)
})
