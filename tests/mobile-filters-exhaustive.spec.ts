import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('every room-count option previews the expected listing count', async ({ page }) => {
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
  await results.getByRole('button', { name: 'Filtros' }).click()

  const cases = [
    ['1 habitación', 9], ['2 habitaciones', 2], ['3 habitaciones', 0], ['4 habitaciones', 2],
    ['5 habitaciones', 3], ['6 habitaciones', 1], ['7 habitaciones', 2], ['8 habitaciones', 1],
    ['9 habitaciones', 1], ['10 habitaciones', 1], ['Más de 10 habitaciones', 1],
  ] as const

  for (const [label, count] of cases) {
    await results.getByRole('button', { name: 'Limpiar' }).click()
    await results.getByLabel(label, { exact: true }).check()
    await expect(results.getByRole('button', { name: new RegExp(`Ver anuncios · ${count}$`) })).toBeVisible()
  }
})
