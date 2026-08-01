import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

async function openResults(page: Page, mode?: 'Vivienda' | 'Turismo') {
  if (mode) await page.getByRole('button', { name: mode, exact: true }).click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  return results
}

async function firstPrices(page: Page) {
  return page.locator('.m2-result-card__price').evaluateAll((nodes) => nodes.slice(0, 3).map((node) => Number((node.textContent ?? '').split('€')[0].replace(/[^0-9]/g, ''))))
}

async function assertNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
}

test('Vivienda and Turismo are the only rental-mode controls and filter real listings', async ({ page }) => {
  await finishOnboarding(page)
  const results = await openResults(page, 'Vivienda')

  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ mes')

  await results.getByRole('button', { name: 'Filtros' }).click()
  const vivienda = results.getByRole('button', { name: 'Vivienda', exact: true })
  const turismo = results.getByRole('button', { name: 'Turismo', exact: true })
  await expect(vivienda).toHaveAttribute('aria-pressed', 'true')
  await expect(turismo).toHaveAttribute('aria-pressed', 'false')
  await expect(results.getByRole('button', { name: 'Comprar' })).toHaveCount(0)
  await expect(results.getByRole('button', { name: 'Alquilar' })).toHaveCount(0)
  await expect(results.getByText('Tipo de inmueble')).toHaveCount(0)
  await expect(results.getByText('Tipo de alquiler')).toHaveCount(0)
  await expect(results.getByLabel('Larga estancia')).toHaveCount(0)

  await turismo.click()
  await expect(turismo).toHaveAttribute('aria-pressed', 'true')
  await expect(results.getByRole('button', { name: /Ver anuncios · 9/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(9)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ noche')

  await results.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Turismo', exact: true })).toHaveAttribute('aria-pressed', 'true')
})

test('price, area, room count and housing type filters change the listing set', async ({ page }) => {
  await finishOnboarding(page)
  const results = await openResults(page, 'Vivienda')
  await results.getByRole('button', { name: 'Filtros' }).click()

  await results.getByLabel('Precio Máx').fill('500')
  await results.getByLabel('Superficie Máx').fill('12')
  await results.getByLabel('1 habitación').check()
  await results.getByLabel('Habitaciones individuales').check()

  const apply = results.getByRole('button', { name: /Ver anuncios · 6/ })
  await expect(apply).toBeVisible()
  await apply.click()
  await expect(results.locator('.m2-result-card')).toHaveCount(6)

  const cards = results.locator('.m2-result-card')
  const count = await cards.count()
  for (let index = 0; index < count; index += 1) {
    const card = cards.nth(index)
    const price = Number(((await card.locator('.m2-result-card__price').textContent()) ?? '').split('€')[0].replace(/[^0-9]/g, ''))
    const facts = (await card.locator('.m2-result-card__facts').textContent()) ?? ''
    const area = Number(facts.match(/(\d+) m²/)?.[1] ?? Number.NaN)
    expect(price).toBeLessThanOrEqual(500)
    expect(area).toBeLessThanOrEqual(12)
    expect(facts).toContain('Habitación individual')
  }

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await expect(results.getByRole('button', { name: /Ver anuncios · 23/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
})

test('sorting, photo carousel, favorites and hiding listings work together', async ({ page }) => {
  await finishOnboarding(page)
  const results = await openResults(page, 'Vivienda')

  await results.getByRole('button', { name: 'Orden' }).click()
  await results.getByRole('radio', { name: 'Más baratos' }).click()
  let prices = await firstPrices(page)
  expect(prices[0]).toBeLessThanOrEqual(prices[1])
  expect(prices[1]).toBeLessThanOrEqual(prices[2])

  await results.getByRole('button', { name: 'Orden' }).click()
  await results.getByRole('radio', { name: 'Más caros' }).click()
  prices = await firstPrices(page)
  expect(prices[0]).toBeGreaterThanOrEqual(prices[1])
  expect(prices[1]).toBeGreaterThanOrEqual(prices[2])

  const firstCard = results.locator('.m2-result-card').first()
  await expect(firstCard.locator('.m2-result-card__counter')).toContainText('1/6')
  await firstCard.locator('.m2-result-card__next').click()
  await expect(firstCard.locator('.m2-result-card__counter')).toContainText('2/6')

  const favorite = firstCard.locator('.m2-result-card__favorite')
  await favorite.click()
  await expect(favorite).toHaveAttribute('aria-pressed', 'true')

  const beforeDiscard = await results.locator('.m2-result-card').count()
  await firstCard.locator('.m2-result-card__discard').click()
  await expect(results.locator('.m2-result-card')).toHaveCount(beforeDiscard - 1)
})

test('contact opens the existing authentication flow and map returns to Google Maps', async ({ page }) => {
  await finishOnboarding(page)
  let results = await openResults(page, 'Vivienda')
  await results.getByRole('button', { name: 'Contactar' }).first().click()
  await expect(page).toHaveURL(/#\/acceso/)
  await expect(page.getByRole('heading', { name: 'Inicia sesión o regístrate' })).toBeVisible()

  await finishOnboarding(page)
  results = await openResults(page, 'Vivienda')
  await results.getByRole('button', { name: 'Mapa' }).click()
  await expect(page.getByTestId('map-search')).toBeVisible({ timeout: 10000 })
})

test('results, sorting and filters fit every supported mobile width', async ({ page }) => {
  for (const width of [320, 360, 390, 430]) {
    await page.setViewportSize({ width, height: 760 })
    await finishOnboarding(page)
    const results = await openResults(page, 'Vivienda')
    await assertNoHorizontalOverflow(page)

    await results.getByRole('button', { name: 'Filtros' }).click()
    await assertNoHorizontalOverflow(page)
    await expect(results.getByRole('button', { name: /Ver anuncios/ })).toBeVisible()
    await results.getByRole('button', { name: /Ver anuncios/ }).click()

    await results.getByRole('button', { name: 'Orden' }).click()
    await assertNoHorizontalOverflow(page)
    await results.getByRole('radio', { name: 'Relevancia' }).click()
    await results.getByRole('button', { name: 'Volver' }).click()
  }
})
