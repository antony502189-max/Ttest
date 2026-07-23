import { expect, test } from '@playwright/test'

test('mobile search filters are fully localized and clamp numeric values', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:language:v1', 'ru'))
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)

  await page.locator('.mobile-filter-control button').click()
  await expect(page.getByText('Тип объекта', { exact: true })).toBeVisible()
  await expect(page.getByText('Цена за ночь', { exact: true })).toBeVisible()
  await expect(page.getByText('Требования к жильцу', { exact: true })).toBeVisible()
  await expect(page.getByText('Минимальная площадь (м²)', { exact: true })).toBeVisible()
  await expect(page.getByText('Максимальная площадь (м²)', { exact: true })).toBeVisible()

  const priceMaximum = page.locator('.filter-price-fields input[type="number"]').nth(1)
  await priceMaximum.fill('05555')
  await priceMaximum.evaluate((element) => (element as HTMLInputElement).blur())
  await expect(priceMaximum).toHaveValue('350')

  const roomMaximum = page.locator('.form-grid--compact input[type="number"]').nth(1)
  await roomMaximum.fill('0588')
  await roomMaximum.evaluate((element) => (element as HTMLInputElement).blur())
  await expect(roomMaximum).toHaveValue('50')

  await expect(page.locator('.filter-footer button').last()).toContainText(/^Показать: \d+ (комната|комнаты|комнат)$/)
  await page.locator('.filter-footer button').last().click()
  await expect(page.locator('#results-title')).toContainText(/^\d+ (комната|комнаты|комнат) в Tenerife$/)

  await page.locator('.mobile-sort-control').click()
  await expect(page.getByText('Сначала старые', { exact: true })).toBeVisible()
  await expect(page.getByText('Сначала дороже', { exact: true })).toBeVisible()
})
