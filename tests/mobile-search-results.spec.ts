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

test('list toolbar opens existing Tenerife listings without a top save button', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await page.getByTestId('search-map').click()

  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Listado' }).click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.getByText(/habitaciones en Tenerife/)).toBeVisible()
  await expect(results.getByText('Habitación luminosa con escritorio y gastos incluidos').first()).toBeVisible()
  await expect(results.locator('.m2-result-card')).toHaveCount(32)
  await expect(results.locator('.m2-result-card img').first()).toBeVisible()
  await expect(results.getByRole('button', { name: 'Guardar', exact: true })).toHaveCount(0)
  await expect(results.getByRole('button', { name: 'Guardar en favoritos' })).toHaveCount(32)

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Turismo' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(9)

  await results.getByRole('button', { name: 'Orden' }).click()
  await expect(results.getByText('Precio más bajo')).toBeVisible()

  await results.getByRole('button', { name: 'Mapa' }).click()
  await expect(results).toHaveCount(0)
  await expect(page.getByTestId('map-search')).toBeVisible()
})

test('mobile results never overflow narrow screens', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await page.getByTestId('search-map').click()
  await page.getByRole('button', { name: 'Listado' }).click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()

  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
})
