import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('desktop canonical room type remains effective on mobile and migrates cleanly', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&habitacion=Estudio')

  const results = page.getByTestId('mobile-results')
  await expect(results.locator('.m2-result-card')).toHaveCount(2)
  for (const text of await results.locator('.m2-result-card__facts').allTextContents()) {
    expect(text).toContain('Estudio')
  }

  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.getByLabel('Estudios', { exact: true })).toBeChecked()
  await results.getByLabel('Precio Máx').fill('1000')
  await results.getByRole('button', { name: /Ver anuncios/ }).click()

  await expect(results.locator('.m2-result-card')).toHaveCount(2)
  expect(new URL(page.url()).hash).toContain('tiposHabitacion=Estudio')
  expect(new URL(page.url()).hash).not.toContain('habitacion=Estudio')
})
