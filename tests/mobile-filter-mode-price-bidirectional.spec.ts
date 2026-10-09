import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('mobile legacy Tourism URLs cannot activate nightly prices or an unsupported rental mode', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&precioMax=5000')
  await expect(page).toHaveURL(/alquiler=long/)
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByRole('button', { name: 'Turismo', exact: true })).toHaveCount(0)
  await expect(results.getByRole('button', { name: 'Vivienda', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(results.getByLabel('Precio Mín')).toHaveValue('0')
  await expect(results.getByLabel('Precio Máx')).toHaveValue('1000')
  await expect(results.getByLabel('Precio Máx')).toHaveAttribute('max', '1000')
})

test('mobile monthly price filter remains bounded when changed and cleared', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByLabel('Precio Máx').fill('500')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(page).toHaveURL(/precioMax=500/)
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await expect(results.getByLabel('Precio Máx')).toHaveValue('1000')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(page).not.toHaveURL(/alquiler=holiday/)
})
