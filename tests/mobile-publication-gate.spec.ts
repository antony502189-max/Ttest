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
  await expect(page.getByRole('heading', { name: 'Войти в аккаунт или зарегистрироваться' })).toBeVisible()
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
  await expect(page.getByText('Управление объектами')).toBeVisible()
})


test('mobile listings action is translated in Spanish, English and Russian', async ({ page }) => {
  const cases = [
    ['es', 'Ver y crear anuncios'],
    ['en', 'View and create listings'],
    ['ru', 'Просмотр и создание объявлений'],
  ] as const

  for (const [language, label] of cases) {
    await page.goto('/#/')
    await page.evaluate(({ language }) => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', language)
      localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    }, { language })
    await page.reload()
    await page.goto('/#/menu')
    await expect(page.getByRole('button', { name: label, exact: true })).toBeVisible()
  }
})

test('authenticated mobile menu separates listing management from profile editing', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })

  await page.goto('/#/menu')
  const properties = page.getByRole('button', { name: 'Просмотр и создание объявлений', exact: true })
  const editProfile = page.getByRole('button', { name: /Редактировать профиль/ })
  await expect(properties).toBeVisible()
  await expect(editProfile).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Управление объектами' })).toBeVisible()

  await properties.click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await page.goto('/#/menu')
  await editProfile.click()
  await expect(page).toHaveURL(/#\/perfil$/)
})


test('route transition removes stale admin immediately and never flashes the full-screen loader while listings load', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo'))
  })

  let delayed = false
  await page.route(/\/src\/pages\/AccountPages\.tsx(?:\?.*)?$/, async (route) => {
    delayed = true
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.continue()
  })

  await page.goto('/#/admin')
  await expect(page.locator('.admin-page')).toBeVisible()

  await page.evaluate(() => { window.location.hash = '#/mis-anuncios' })
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.admin-page')).toHaveCount(0)
  await expect(page.locator('.route-loading')).toHaveCount(0)
  await expect(page.locator('.route-transition-loading')).toBeVisible()

  await expect.poll(() => delayed).toBe(true)
  await expect(page.locator('.route-transition-loading')).toHaveCount(0)
  await expect(page.locator('.route-loading')).toHaveCount(0)
  await expect(page.locator('.admin-page')).toHaveCount(0)
})

test('publish transition from admin never flashes the full-screen loader', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo'))
  })

  await page.route(/\/src\/pages\/ListingCreatePage\.tsx(?:\?.*)?$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.continue()
  })

  await page.goto('/#/admin')
  await expect(page.locator('.admin-page')).toBeVisible()

  await page.evaluate(() => { window.location.hash = '#/publicar' })
  await expect(page).toHaveURL(/#\/publicar$/)
  await expect(page.locator('.admin-page')).toHaveCount(0)
  await expect(page.locator('.route-loading')).toHaveCount(0)
  await expect(page.locator('.route-transition-loading')).toBeVisible()
  await expect(page.locator('.listing-create-page')).toBeVisible()
  await expect(page.locator('.route-transition-loading')).toHaveCount(0)
})
