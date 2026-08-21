import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('removed customer filters stay absent and legacy route values are canonicalized away', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&panel=filtros&habitaciones=2&tamanoMin=18&tamanoMax=25&servicios=Aire%20acondicionado%7CPiscina')
  const panel = page.locator('.m2-results-filter')
  await expect(panel).toBeVisible()
  await expect(panel.getByText('Número de habitaciones', { exact: true })).toHaveCount(0)
  await expect(panel.getByText('Aire acondicionado', { exact: true })).toHaveCount(0)
  await expect(panel.getByText('Superficie', { exact: true })).toHaveCount(0)
  await expect.poll(() => page.url()).not.toContain('habitaciones=')
  await expect.poll(() => page.url()).not.toContain('tamanoMin=')
  await expect.poll(() => page.url()).not.toContain('tamanoMax=')
  await expect.poll(() => page.url()).not.toContain('Aire%20acondicionado')
  await expect.poll(() => page.url()).toContain('Piscina')
})

test('favorite listing has an explicit remove action that removes it from Favorites', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const firstFavorite = page.locator('.favorite-button').first()
  await expect(firstFavorite).toBeVisible()
  await firstFavorite.click()
  await page.goto('/#/favoritos')
  const remove = page.getByRole('button', { name: /Eliminar .* de favoritos/ }).first()
  await expect(remove).toBeVisible()
  await remove.click()
  await expect(page.getByText('0 habitaciones guardadas', { exact: true })).toBeVisible()
  await expect(page.getByText('Eliminar de favoritos', { exact: true })).toHaveCount(0)
})
