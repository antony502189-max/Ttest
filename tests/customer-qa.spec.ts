import { expect, test } from '@playwright/test'

test('mobile search filters are fully localized and clamp numeric values', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')

  await page.getByTestId('mobile-results').getByRole('button', { name: 'Фильтры' }).click()
  const filters = page.locator('.m2-results-filter')
  await expect(filters).toBeVisible()
  await expect(filters).toContainText('Цена')
  await expect(filters).toContainText('Площадь')
  await expect(filters).toContainText('Количество комнат')
  await expect(filters).toContainText('Тип жилья')

  const numericInputs = filters.locator('input[type="number"]')
  await numericInputs.nth(0).fill('-5')
  await expect(numericInputs.nth(0)).toHaveValue('0')
  await numericInputs.nth(1).fill('05555')
  await expect(numericInputs.nth(1)).toHaveValue('5555')
  await numericInputs.nth(2).fill('-8')
  await expect(numericInputs.nth(2)).toHaveValue('0')

  await filters.locator('footer button').click()
  await expect(page.locator('.m2-results__list')).toBeVisible()

  await page.locator('.m2-results__toolbar button').nth(1).click()
  await expect(page.locator('.m2-results-sort [role="radio"]')).toHaveCount(12)
  await expect(page.locator('.m2-results-sort')).toContainText('Дорогие')
})
