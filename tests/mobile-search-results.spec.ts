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

async function firstPrices(page: Page) {
  return page.locator('.m2-result-card__price').evaluateAll((nodes) => nodes.slice(0, 3).map((node) => Number((node.textContent ?? '').replace(/[^0-9]/g, ''))))
}

test('main search opens repository listings with working sorting and filters', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()

  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.locator('.m2-result-card')).toHaveCount(32)
  await expect(results.locator('.m2-result-card img').first()).toBeVisible()
  await expect(results.getByRole('button', { name: 'Guardar', exact: true })).toHaveCount(0)

  await results.getByRole('button', { name: 'Orden' }).click()
  await expect(results.getByRole('radio', { name: 'Más baratos' })).toBeVisible()
  await results.getByRole('radio', { name: 'Más baratos' }).click()
  const prices = await firstPrices(page)
  expect(prices[0]).toBeLessThanOrEqual(prices[1])
  expect(prices[1]).toBeLessThanOrEqual(prices[2])

  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByRole('button', { name: 'Comprar' })).toBeVisible()
  await expect(results.getByRole('button', { name: 'Alquilar' })).toBeVisible()
  await expect(results.getByText('Número de habitaciones')).toBeVisible()
  await results.getByLabel('1 habitación').check()
  const apply = results.getByRole('button', { name: /Ver anuncios/ })
  await expect(apply).toBeVisible()
  await apply.click()
  await expect(results.locator('.m2-result-card')).not.toHaveCount(0)

  const beforeDiscard = await results.locator('.m2-result-card').count()
  const favorite = results.locator('.m2-result-card__favorite').first()
  await favorite.click()
  await expect(favorite).toHaveAttribute('aria-pressed', 'true')
  await results.locator('.m2-result-card__discard').first().click()
  await expect(results.locator('.m2-result-card')).toHaveCount(beforeDiscard - 1)

  await results.getByRole('button', { name: 'Mapa' }).click()
  await expect(page.getByTestId('map-search')).toBeVisible({ timeout: 10000 })
})

test('rent filters include long stay and tourism while buy mode hides rental type', async ({ page }) => {
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByText('Tipo de alquiler')).toBeVisible()
  await expect(results.getByLabel('Larga estancia')).toBeVisible()
  await expect(results.getByLabel('Turismo')).toBeVisible()
  await results.getByRole('button', { name: 'Comprar' }).click()
  await expect(results.getByText('Tipo de alquiler')).toHaveCount(0)
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(32)
})

test('results and panels do not overflow narrow mobile screens', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await finishOnboarding(page)
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await page.getByRole('button', { name: 'Filtros' }).click()
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
})
