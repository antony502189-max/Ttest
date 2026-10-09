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

async function openLongStayResults(page: Page) {
  await finishOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()
  const results = page.getByTestId('mobile-results')
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ mes')
  return results
}

test('closing filters discards an unapplied long-term price change', async ({ page }) => {
  const results = await openLongStayResults(page)
  const before = page.url()
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByLabel('Precio Máx').fill('500')
  await expect(results.getByRole('button', { name: /Ver anuncios/ })).toBeVisible()
  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(page).toHaveURL(before)
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByLabel('Precio Máx')).toHaveValue('1000')
  await expect(results.getByRole('button', { name: 'Vivienda', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(results.getByRole('button', { name: 'Turismo', exact: true })).toHaveCount(0)
})

test('applying a residential draft commits price to URL, results and reload', async ({ page }) => {
  const results = await openLongStayResults(page)
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByLabel('Precio Máx').fill('500')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(page).toHaveURL(/precioMax=500/)
  await expect(results.locator('.m2-result-card').first()).toBeVisible()
  const filteredCount = await results.locator('.m2-result-card').count()
  expect(filteredCount).toBeGreaterThan(0)
  expect(filteredCount).toBeLessThan(23)
  await page.reload()
  const restored = page.getByTestId('mobile-results')
  await expect(restored).toBeVisible()
  await expect(restored.locator('.m2-result-card')).toHaveCount(filteredCount)
  await expect(restored.locator('.m2-result-card__price').first()).toContainText('/ mes')
})


test('clear is a draft action until View listings is pressed', async ({ page }) => {
  const results = await openLongStayResults(page)

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

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await expect(results.getByRole('button', { name: /Ver anuncios · 23/ })).toBeVisible()
  await results.getByRole('button', { name: 'Cerrar' }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(filteredCount)

  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByLabel('Precio Máx')).toHaveValue('500')
  await expect(results.getByLabel('Habitaciones individuales')).toBeChecked()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
})
