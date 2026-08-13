import { expect, test, type Locator, type Page } from '@playwright/test'

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

async function openLongResults(page: Page) {
  await finishOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  return results
}

async function openFilters(results: Locator) {
  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.locator('.m2-results-filter')).toBeVisible()
}

function parsePrice(text: string) {
  return Number(text.split('€')[0].replace(/[^0-9]/g, ''))
}

function parseArea(text: string) {
  return Number(text.match(/(\d+) m²/)?.[1] ?? Number.NaN)
}

function parseBedrooms(text: string) {
  return Number(text.match(/·\s*(\d+)\s+habitaci/)?.[1] ?? Number.NaN)
}

async function cardTexts(results: Locator) {
  return results.locator('.m2-result-card__facts').allTextContents()
}

async function cardPrices(results: Locator) {
  const texts = await results.locator('.m2-result-card__price').allTextContents()
  return texts.map(parsePrice)
}

async function apply(results: Locator) {
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-results-filter')).toHaveCount(0)
}

test('price filter handles min, max, inverted boundaries and persists normalized URL state', async ({ page }) => {
  const results = await openLongResults(page)
  await openFilters(results)
  await results.getByLabel('Precio Mín').fill('500')
  await results.getByLabel('Precio Máx').fill('650')
  await apply(results)

  let prices = await cardPrices(results)
  expect(prices.length).toBeGreaterThan(0)
  for (const price of prices) expect(price).toBeGreaterThanOrEqual(500)
  for (const price of prices) expect(price).toBeLessThanOrEqual(650)
  expect(new URL(page.url()).hash).toContain('precioMin=500')
  expect(new URL(page.url()).hash).toContain('precioMax=650')

  await openFilters(results)
  await results.getByLabel('Precio Mín').fill('700')
  await results.getByLabel('Precio Máx').fill('400')
  await apply(results)

  prices = await cardPrices(results)
  expect(prices.length).toBeGreaterThan(0)
  for (const price of prices) expect(price).toBeGreaterThanOrEqual(400)
  for (const price of prices) expect(price).toBeLessThanOrEqual(700)
  const hash = new URL(page.url()).hash
  expect(hash).toContain('precioMin=400')
  expect(hash).toContain('precioMax=700')

  await page.reload()
  const restored = page.getByTestId('mobile-results')
  await expect(restored).toBeVisible()
  prices = await cardPrices(restored)
  for (const price of prices) expect(price).toBeGreaterThanOrEqual(400)
  for (const price of prices) expect(price).toBeLessThanOrEqual(700)
})

test('area filter handles normal and inverted ranges and never leaks missing-size listings', async ({ page }) => {
  const results = await openLongResults(page)
  await openFilters(results)
  await results.getByLabel('Superficie Mín').fill('10')
  await results.getByLabel('Superficie Máx').fill('15')
  await apply(results)

  let facts = await cardTexts(results)
  expect(facts.length).toBeGreaterThan(0)
  for (const text of facts) {
    const area = parseArea(text)
    expect(Number.isFinite(area)).toBe(true)
    expect(area).toBeGreaterThanOrEqual(10)
    expect(area).toBeLessThanOrEqual(15)
  }

  await openFilters(results)
  await results.getByLabel('Superficie Mín').fill('18')
  await results.getByLabel('Superficie Máx').fill('8')
  await apply(results)
  facts = await cardTexts(results)
  for (const text of facts) {
    const area = parseArea(text)
    expect(area).toBeGreaterThanOrEqual(8)
    expect(area).toBeLessThanOrEqual(18)
  }
  const hash = new URL(page.url()).hash
  expect(hash).toContain('tamanoMin=8')
  expect(hash).toContain('tamanoMax=18')
})

test('every room-count option previews and filters the deterministic listing set correctly', async ({ page }) => {
  const results = await openLongResults(page)
  await openFilters(results)

  const cases = [
    ['1 habitación', 9, 1],
    ['2 habitaciones', 2, 2],
    ['3 habitaciones', 0, 3],
    ['4 habitaciones', 2, 4],
    ['5 habitaciones', 3, 5],
    ['6 habitaciones', 1, 6],
    ['7 habitaciones', 2, 7],
    ['8 habitaciones', 1, 8],
    ['9 habitaciones', 1, 9],
    ['10 habitaciones', 1, 10],
    ['Más de 10 habitaciones', 1, 11],
  ] as const

  for (const [label, expectedCount, bedroom] of cases) {
    await results.getByRole('button', { name: 'Limpiar' }).click()
    await results.getByLabel(label).check()
    await expect(results.getByRole('button', { name: new RegExp(`Ver anuncios · ${expectedCount}$`) })).toBeVisible()

    if (expectedCount > 0) {
      await apply(results)
      const facts = await cardTexts(results)
      expect(facts).toHaveLength(expectedCount)
      for (const text of facts) {
        const count = parseBedrooms(text)
        if (bedroom === 11) expect(count).toBeGreaterThan(10)
        else expect(count).toBe(bedroom)
      }
      await openFilters(results)
    }
  }

  await results.getByRole('button', { name: 'Cerrar' }).click()
})

test('every housing type works alone and multiple types use OR semantics', async ({ page }) => {
  const results = await openLongResults(page)
  const cases = [
    ['Habitaciones individuales', 'Habitación individual', 19],
    ['Habitaciones compartidas', 'Habitación compartida', 2],
    ['Estudios', 'Estudio', 2],
  ] as const

  for (const [label, fact, expectedCount] of cases) {
    await openFilters(results)
    await results.getByRole('button', { name: 'Limpiar' }).click()
    await results.getByLabel(label).check()
    await expect(results.getByRole('button', { name: new RegExp(`Ver anuncios · ${expectedCount}$`) })).toBeVisible()
    await apply(results)
    const texts = await cardTexts(results)
    expect(texts).toHaveLength(expectedCount)
    for (const text of texts) expect(text).toContain(fact)
  }

  await openFilters(results)
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await results.getByLabel('Habitaciones compartidas').check()
  await results.getByLabel('Estudios').check()
  await expect(results.getByRole('button', { name: /Ver anuncios · 4$/ })).toBeVisible()
  await apply(results)
  const texts = await cardTexts(results)
  expect(texts).toHaveLength(4)
  for (const text of texts) expect(text.includes('Habitación compartida') || text.includes('Estudio')).toBe(true)
})

test('combined filters use AND semantics and clear/cancel/apply boundaries stay correct', async ({ page }) => {
  const results = await openLongResults(page)
  await openFilters(results)
  await results.getByLabel('Precio Máx').fill('500')
  await results.getByLabel('Superficie Máx').fill('12')
  await results.getByLabel('1 habitación').check()
  await results.getByLabel('Habitaciones individuales').check()
  await expect(results.getByRole('button', { name: /Ver anuncios · 6$/ })).toBeVisible()

  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)

  await openFilters(results)
  await expect(results.getByRole('button', { name: /Ver anuncios · 23$/ })).toBeVisible()
  await results.getByLabel('Precio Máx').fill('500')
  await results.getByLabel('Superficie Máx').fill('12')
  await results.getByLabel('1 habitación').check()
  await results.getByLabel('Habitaciones individuales').check()
  await apply(results)
  await expect(results.locator('.m2-result-card')).toHaveCount(6)

  const prices = await cardPrices(results)
  const facts = await cardTexts(results)
  for (const price of prices) expect(price).toBeLessThanOrEqual(500)
  for (const text of facts) {
    expect(parseArea(text)).toBeLessThanOrEqual(12)
    expect(parseBedrooms(text)).toBe(1)
    expect(text).toContain('Habitación individual')
  }

  await openFilters(results)
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await expect(results.getByRole('button', { name: /Ver anuncios · 23$/ })).toBeVisible()
  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(6)

  await openFilters(results)
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await apply(results)
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
})

test('rental mode is a draft until apply and survives reload only after commit', async ({ page }) => {
  const results = await openLongResults(page)
  await openFilters(results)
  const tourism = results.getByRole('button', { name: 'Turismo', exact: true })
  await tourism.click()
  await expect(results.getByRole('button', { name: /Ver anuncios · 9$/ })).toBeVisible()
  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ mes')

  await openFilters(results)
  await results.getByRole('button', { name: 'Turismo', exact: true }).click()
  await apply(results)
  await expect(results.locator('.m2-result-card')).toHaveCount(9)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ noche')
  expect(new URL(page.url()).hash).toContain('alquiler=holiday')

  await page.reload()
  const restored = page.getByTestId('mobile-results')
  await expect(restored.locator('.m2-result-card')).toHaveCount(9)
  await expect(restored.locator('.m2-result-card__price').first()).toContainText('/ noche')
})

test('filter panel has no horizontal overflow at every supported mobile width', async ({ page }) => {
  for (const width of [320, 360, 375, 390, 430]) {
    await page.setViewportSize({ width, height: 760 })
    const results = await openLongResults(page)
    await openFilters(results)
    const sizes = await page.evaluate(() => ({
      viewport: innerWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      panel: document.querySelector<HTMLElement>('.m2-results-filter')?.scrollWidth ?? 0,
    }))
    expect(sizes.document).toBeLessThanOrEqual(sizes.viewport)
    expect(sizes.body).toBeLessThanOrEqual(sizes.viewport)
    expect(sizes.panel).toBeLessThanOrEqual(sizes.viewport)
    await results.getByRole('button', { name: 'Cerrar' }).click()
    await results.getByRole('button', { name: 'Volver' }).click()
  }
})
