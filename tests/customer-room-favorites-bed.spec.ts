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

test('favorites trash action enters selection mode and removes only selected cards', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')

  const favoriteButtons = page.locator('.favorite-button')
  await expect(favoriteButtons.first()).toBeVisible()
  await favoriteButtons.nth(0).click()
  await favoriteButtons.nth(1).click()

  await page.goto('/#/favoritos')
  await expect(page.getByText('2 habitaciones guardadas', { exact: true })).toBeVisible()

  const startDelete = page.getByRole('button', { name: 'Seleccionar favoritos para eliminar' })
  await expect(startDelete).toBeVisible()
  await startDelete.click()

  const selectors = page.locator('.favorite-card__selector')
  await expect(selectors).toHaveCount(2)
  await expect(page.getByText('0 seleccionados', { exact: true })).toBeVisible()

  await selectors.first().click()
  await expect(selectors.first()).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('1 seleccionado', { exact: true })).toBeVisible()

  const removeSelected = page.getByRole('button', { name: 'Eliminar seleccionados (1)' })
  await expect(removeSelected).toBeEnabled()
  await removeSelected.click()

  await expect(page.getByText('1 habitación guardada', { exact: true })).toBeVisible()
  await expect(page.locator('.favorite-card')).toHaveCount(1)
  await expect(page.locator('.favorite-card__selector')).toHaveCount(0)
})

test('favorites selection mode is localized and functional in Russian on mobile', async ({ page }) => {
  // Seed one favorite with the existing desktop result control, then open the
  // dedicated mobile Favorites shell where the customer-facing trash workflow lives.
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const favoriteButton = page.locator('.favorite-button').first()
  await expect(favoriteButton).toBeVisible()
  await favoriteButton.click()

  await page.evaluate(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await page.goto('/#/favoritos')

  await expect(page.getByText('Избранное и списки', { exact: true })).toBeVisible()
  const startDelete = page.getByRole('button', { name: 'Выбрать избранное для удаления' })
  await expect(startDelete).toBeVisible()
  await startDelete.click()

  await expect(page.getByText('Выбрано: 0', { exact: true })).toBeVisible()
  const favoriteRow = page.locator('.m2-collection__list > button').first()
  await expect(favoriteRow).toHaveAttribute('aria-pressed', 'false')
  await favoriteRow.click()
  await expect(favoriteRow).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('Выбрано: 1', { exact: true })).toBeVisible()

  const removeSelected = page.getByRole('button', { name: 'Удалить выбранные (1)' })
  await expect(removeSelected).toBeEnabled()
  await removeSelected.click()

  await expect(page.getByText('У вас нет объектов в избранном', { exact: true })).toBeVisible()
  await expect(page.locator('.m2-collection__list > button')).toHaveCount(0)
})
