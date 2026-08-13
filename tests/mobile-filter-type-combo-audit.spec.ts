import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function resultsPage(page: import('@playwright/test').Page) {
  await page.goto('/')
  if (!(await page.getByTestId('open-location').isVisible().catch(() => false))) {
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Ahora no' }).click()
  }
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()
  return page.getByTestId('mobile-results')
}

async function openFilters(results: import('@playwright/test').Locator) {
  await results.getByRole('button', { name: 'Filtros' }).click()
}

test('each housing type filters correctly and multiple types use OR semantics', async ({ page }) => {
  const results = await resultsPage(page)
  const cases = [
    ['Habitaciones individuales', 'Habitación individual', 19],
    ['Habitaciones compartidas', 'Habitación compartida', 2],
    ['Estudios', 'Estudio', 2],
  ] as const

  for (const [label, fact, expected] of cases) {
    await openFilters(results)
    await results.getByRole('button', { name: 'Limpiar' }).click()
    await results.getByLabel(label, { exact: true }).check()
    await expect(results.getByRole('button', { name: new RegExp(`Ver anuncios · ${expected}$`) })).toBeVisible()
    await results.getByRole('button', { name: /Ver anuncios/ }).click()
    await expect(results.locator('.m2-result-card')).toHaveCount(expected)
    for (const text of await results.locator('.m2-result-card__facts').allTextContents()) expect(text).toContain(fact)
  }

  await openFilters(results)
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await results.getByLabel('Habitaciones compartidas', { exact: true }).check()
  await results.getByLabel('Estudios', { exact: true }).check()
  await expect(results.getByRole('button', { name: /Ver anuncios · 4$/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(4)
  for (const text of await results.locator('.m2-result-card__facts').allTextContents()) {
    expect(text.includes('Habitación compartida') || text.includes('Estudio')).toBe(true)
  }
})

test('price, area, bedroom and housing type combine with AND semantics', async ({ page }) => {
  const results = await resultsPage(page)
  await openFilters(results)
  await results.getByLabel('Precio Máx').fill('500')
  await results.getByLabel('Superficie Máx').fill('12')
  await results.getByLabel('1 habitación', { exact: true }).check()
  await results.getByLabel('Habitaciones individuales', { exact: true }).check()
  await expect(results.getByRole('button', { name: /Ver anuncios · 6$/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(6)

  const prices = await results.locator('.m2-result-card__price').allTextContents()
  const facts = await results.locator('.m2-result-card__facts').allTextContents()
  for (const text of prices) expect(Number(text.split('€')[0].replace(/[^0-9]/g, ''))).toBeLessThanOrEqual(500)
  for (const text of facts) {
    expect(Number(text.match(/(\d+) m²/)?.[1] ?? Number.NaN)).toBeLessThanOrEqual(12)
    expect(text).toContain('· 1 habitación')
    expect(text).toContain('Habitación individual')
  }
})
