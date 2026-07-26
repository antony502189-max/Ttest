import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishRussianOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Русский' }).click()
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Сейчас нет' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test('publication gate has no duplicate top notice or close icon and opens existing auth', async ({ page }) => {
  await finishRussianOnboarding(page)
  await page.getByRole('button', { name: 'Разместить объявление' }).click()

  const gate = page.getByTestId('publication-gate')
  await expect(gate).toBeVisible()
  await expect(gate.locator('header')).toContainText('Разместите объявление')
  await expect(gate.locator('header')).not.toContainText('Для публикации объявления войдите в аккаунт')
  await expect(gate.locator('header button')).toHaveCount(1)
  await expect(gate.locator('header button')).toHaveAttribute('aria-label', 'Назад')
  await expect(gate.getByRole('button', { name: 'Закрыть' })).toHaveCount(0)
  await expect(gate.getByRole('heading', { name: 'Для публикации объявления войдите в аккаунт' })).toBeVisible()

  await gate.getByRole('button', { name: 'Войти в аккаунт' }).click()
  await expect(page).toHaveURL(/#\/acceso/)
  await expect(page.getByRole('heading', { name: 'С возвращением' })).toBeVisible()
})

test('publication entry in menu opens the same clean gate', async ({ page }) => {
  await finishRussianOnboarding(page)
  await page.getByRole('button', { name: 'Меню' }).click()
  await page.getByRole('button', { name: /Опубликовать своё объявление/ }).click()

  const gate = page.getByTestId('publication-gate')
  await expect(gate).toBeVisible()
  await expect(gate.locator('header')).not.toContainText('Для публикации объявления войдите в аккаунт')
  await gate.getByRole('button', { name: 'Назад' }).click()
  await expect(gate).toHaveCount(0)
  await expect(page.getByText('Ваши объекты')).toBeVisible()
})
