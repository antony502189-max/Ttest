import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('removed room-size and room-count controls stay absent while bunk bed remains selectable', async ({ page }) => {
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

  await expect(results.getByText('Número de habitaciones', { exact: true })).toHaveCount(0)
  await expect(results.getByText('Superficie', { exact: true })).toHaveCount(0)
  await expect(results.getByText('Aire acondicionado', { exact: true })).toHaveCount(0)
  const bed = results.getByLabel('Tipo de cama')
  await expect(bed).toBeVisible()
  await bed.selectOption('bunk')
  await expect(bed).toHaveValue('bunk')
  await expect(results).toContainText('Litera')
})
