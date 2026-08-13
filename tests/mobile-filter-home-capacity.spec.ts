import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('two-person capacity survives price filter, apply and reload', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/')
  await page.locator('.m2-occupant-trigger').click()
  await page.locator('[data-m2-occupant-key="two"]').click()
  await page.locator('.m2-custom-occupant-done').click()
  await page.getByTestId('open-location').click()

  const results = page.getByTestId('mobile-results')
  await expect(results.locator('.m2-result-card')).toHaveCount(8)
  for (const card of await results.locator('.m2-result-card').all()) {
    await expect(card).toContainText('Habitación para 2 personas')
  }

  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByLabel('Precio Máx').fill('500')
  await expect(results.getByRole('button', { name: /Ver anuncios · 3$/ })).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(results.locator('.m2-result-card')).toHaveCount(3)
  expect(new URL(page.url()).hash).toContain('capacidad=2')
  expect(new URL(page.url()).hash).toContain('precioMax=500')

  await page.reload()
  const restored = page.getByTestId('mobile-results')
  await expect(restored.locator('.m2-result-card')).toHaveCount(3)
  for (const card of await restored.locator('.m2-result-card').all()) {
    await expect(card).toContainText('Habitación para 2 personas')
  }
})
