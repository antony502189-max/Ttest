import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('Tourism nightly price never becomes a Long Stay monthly constraint', async ({ page }) => {
  await page.goto('/')
  if (!(await page.getByTestId('open-location').isVisible().catch(() => false))) {
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Continuar' }).click()
    await page.getByRole('button', { name: 'Ahora no' }).click()
  }
  await page.locator('.m2-mode-switch > button').nth(1).click()
  await page.getByTestId('open-location').click()

  const results = page.getByTestId('mobile-results')
  await expect(results.locator('.m2-result-card')).toHaveCount(9)
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByLabel('Precio Máx').fill('70')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  expect(await results.locator('.m2-result-card').count()).toBeGreaterThan(0)

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Vivienda', exact: true }).click()
  await expect(results.getByLabel('Precio Mín')).toHaveValue('0')
  await expect(results.getByLabel('Precio Máx')).toHaveValue('1200')
  await expect(results.getByRole('button', { name: /Ver anuncios · 23$/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(23)
  await expect(results.locator('.m2-result-card__price').first()).toContainText('/ mes')
})
