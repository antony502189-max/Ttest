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

test('drawn-zone search opens the filtered listing results instead of staying on the map', async ({ page }) => {
  await finishOnboarding(page)
  const polygon = '27.50000,-17.50000;27.50000,-15.50000;29.00000,-15.50000;29.00000,-17.50000'
  await page.goto(`/#/buscar?q=Tenerife&vista=mapa&poligono=${encodeURIComponent(polygon)}`)

  const searchArea = page.getByTestId('search-this-area')
  await expect(searchArea).toBeVisible({ timeout: 20_000 })
  await searchArea.click()

  await expect(page).toHaveURL(/#\/buscar\?/)
  await expect(page).not.toHaveURL(/(?:\?|&)vista=mapa(?:&|$)/)
  await expect(page).toHaveURL(/poligono=/)

  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.locator('.m2-result-card').first()).toBeVisible()
})
