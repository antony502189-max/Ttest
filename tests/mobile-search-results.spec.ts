import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  await expect.poll(async () => (await page.getByTestId('open-location').isVisible().catch(() => false)) || (await page.getByRole('button', { name: 'Continuar' }).first().isVisible().catch(() => false))).toBe(true)
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

const homeModeButton = (page: Page, mode: 'Vivienda' | 'Turismo') =>
  page.locator('.m2-mode-switch > button').nth(mode === 'Vivienda' ? 0 : 1)

async function openResults(page: Page, mode?: 'Vivienda' | 'Turismo') {
  if (mode) await homeModeButton(page, mode).click()
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

test('Vivienda is the sole mode and mobile filters never show Tourism', async ({ page }) => {
  await finishOnboarding(page)
  const modes = page.locator('.m2-mode-switch > button')
  await expect(modes).toHaveCount(1)
  await modes.first().click()
  const results = await openResults(page)
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ mes')
  await results.getByRole('button', { name: 'Filtros' }).click()
  const housing = results.getByRole('button', { name: 'Vivienda', exact: true })
  await expect(housing).toHaveAttribute('aria-pressed', 'true')
  await expect(results.getByRole('button', { name: 'Turismo', exact: true })).toHaveCount(0)
  await expect(results.getByLabel('Precio Máx')).toHaveAttribute('max', '1000')
  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await results.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)
  await expect(modes.first()).toHaveAttribute('aria-pressed', 'true')
})

test('price and housing type filters change the listing set', async ({ page }) => {
  await finishOnboarding(page)
  const results = await openResults(page, 'Vivienda')
  await results.getByRole('button', { name: 'Filtros' }).click()

  await results.getByLabel('Precio Máx').fill('500')
  await results.getByLabel('Habitaciones individuales').check()

  const apply = results.getByRole('button', { name: /Ver anuncios · \d+/ })
  await expect(apply).toBeVisible()
  const filteredCount = Number((await apply.textContent())?.match(/(\d+)$/)?.[1] ?? 0)
  expect(filteredCount).toBeGreaterThan(0)
  expect(filteredCount).toBeLessThan(23)
  await apply.click()
  await expect(results.locator('.m2-result-card')).toHaveCount(filteredCount)

  const cards = results.locator('.m2-result-card')
  const count = await cards.count()
  for (let index = 0; index < count; index += 1) {
    const card = cards.nth(index)
    const price = Number(((await card.locator('.m2-result-card__price').textContent()) ?? '').split('€')[0].replace(/[^0-9]/g, ''))
    const facts = (await card.locator('.m2-result-card__facts').textContent()) ?? ''
    expect(price).toBeLessThanOrEqual(500)
    expect(facts).toContain('Habitación individual')
  }

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await expect(results.getByRole('button', { name: /Ver anuncios · 23/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
})

test('sorting, photo carousel and favorites work without a delete-like guest affordance', async ({ page }) => {
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
  const firstPhoto = firstCard.locator('.m2-result-card__media img')
  const initialImageUrl = await firstPhoto.getAttribute('src')
  await firstCard.locator('.m2-result-card__next').click()
  await expect(firstCard.locator('.m2-result-card__counter')).toContainText('2/6')
  // The rendered URL must advance with the counter even if image decoding or
  // fetching the next network frame is still in progress.
  expect(initialImageUrl).toBeTruthy()
  await expect(firstPhoto).not.toHaveAttribute('src', initialImageUrl!)

  const favorite = firstCard.locator('.m2-result-card__favorite')
  await favorite.click()
  await expect(favorite).toHaveAttribute('aria-pressed', 'true')

  // Public/guest cards must not expose a trash-shaped control. Actual hard
  // deletion belongs to authenticated management surfaces and is API-gated.
  await expect(firstCard.locator('.m2-result-card__discard')).toBeHidden()
  await expect(firstCard.getByRole('button', { name: 'Ocultar anuncio' })).toBeHidden()
})

test('contact opens the public listing contact area and map returns to Google Maps', async ({ page }) => {
  await finishOnboarding(page)
  let results = await openResults(page, 'Vivienda')
  await results.getByRole('button', { name: 'Contactar' }).first().click()
  await expect(page).toHaveURL(/#\/habitacion\/.+#contacto/)

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
