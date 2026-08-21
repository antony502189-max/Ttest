import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function openFilters(page: import('@playwright/test').Page) {
  await page.goto('/')
  if (!(await page.getByTestId('open-location').isVisible().catch(() => false))) {
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Ahora no' }).click()
  }
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await results.getByRole('button', { name: 'Filtros' }).click()
  return results
}

test('price range normalizes inverted bounds and survives reload', async ({ page }) => {
  const results = await openFilters(page)
  await results.getByLabel('Precio Mín').fill('700')
  await results.getByLabel('Precio Máx').fill('400')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()

  const hash = new URL(page.url()).hash
  expect(hash).toContain('precioMin=400')
  expect(hash).toContain('precioMax=700')

  const prices = await results.locator('.m2-result-card__price').allTextContents()
  expect(prices.length).toBeGreaterThan(0)
  for (const text of prices) {
    const value = Number(text.split('€')[0].replace(/[^0-9]/g, ''))
    expect(value).toBeGreaterThanOrEqual(400)
    expect(value).toBeLessThanOrEqual(700)
  }

  await page.reload()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  expect(new URL(page.url()).hash).toContain('precioMin=400')
  expect(new URL(page.url()).hash).toContain('precioMax=700')
})

test('long-stay price never leaks into Tourism when cadence changes', async ({ page }) => {
  const results = await openFilters(page)
  await results.getByLabel('Precio Mín').fill('600')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Turismo', exact: true }).click()
  await expect(results.getByLabel('Precio Mín')).toHaveValue('0')
  await expect(results.getByLabel('Precio Máx')).toHaveValue('1200')
  await expect(results.getByRole('button', { name: /Ver anuncios · 9$/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(9)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ noche')
})
