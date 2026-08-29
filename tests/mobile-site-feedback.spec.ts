import { expect, test, type Page } from '@playwright/test'

async function openMobile(page: Page, route = '/#/') {
  await page.setViewportSize({ width: 320, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto(route)
  await page.reload()
}

test('mobile move-out date is retained, persisted in URL and does not overflow', async ({ page }) => {
  await openMobile(page, '/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  const dates = page.locator('.m2-results-filter__pair--dates input[type="date"]')
  await expect(dates).toHaveCount(2)

  await dates.nth(0).fill('2026-08-15')
  await dates.nth(1).fill('2026-09-15')
  await expect(dates.nth(0)).toHaveValue('2026-08-15')
  await expect(dates.nth(1)).toHaveValue('2026-09-15')

  const fits = await page.locator('.m2-results-filter__pair--dates > label').evaluateAll((labels) => labels.every((label) => label.scrollWidth <= label.clientWidth))
  expect(fits).toBe(true)

  await page.locator('.m2-results-filter > footer button').click()
  await expect(page).toHaveURL(/fecha=2026-08-15/)
  await expect(page).toHaveURL(/hasta=2026-09-15/)
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
})

test('mobile home exposes pets and smoking filters and carries them into search', async ({ page }) => {
  await openMobile(page)
  const pets = page.getByTestId('mobile-home-pets-yes')
  const smoking = page.getByTestId('mobile-home-smoking-yes')
  await expect(pets).toBeVisible()
  await expect(smoking).toBeVisible()

  await pets.click()
  await expect(pets).toHaveAttribute('aria-pressed', 'true')
  await page.getByTestId('open-location').click()
  await expect(page).toHaveURL(/buscar/)
  expect(new URL(page.url().replace('/#/', '/')).searchParams.get('mascotas')).toBe('Sí')
})

test('persisted home access filters stay visible after reload and the first tap clears them', async ({ page }) => {
  await openMobile(page)
  const pets = page.getByTestId('mobile-home-pets-yes')
  await pets.click()
  await expect(pets).toHaveAttribute('aria-pressed', 'true')

  await page.reload()
  const reloadedPets = page.getByTestId('mobile-home-pets-yes')
  await expect(reloadedPets).toHaveAttribute('aria-pressed', 'true')
  await reloadedPets.click()
  await expect(reloadedPets).toHaveAttribute('aria-pressed', 'false')

  await page.getByTestId('open-location').click()
  await expect(page).toHaveURL(/buscar/)
  expect(new URL(page.url().replace('/#/', '/')).searchParams.get('mascotas')).toBeNull()
})

test('appearance row opens three choices and applies selected theme', async ({ page }) => {
  await openMobile(page, '/#/menu')
  const trigger = page.getByTestId('mobile-appearance-trigger')
  await expect(trigger).toBeVisible()
  await trigger.click()

  const choices = page.locator('.m2-appearance-dialog [role="radio"]')
  await expect(choices).toHaveCount(3)
  await choices.nth(1).click()
  await expect(page.locator('html')).toHaveClass(/site-theme-dark/)

  await trigger.click()
  await choices.nth(0).click()
  await expect(page.locator('html')).toHaveClass(/site-theme-light/)
})

test('dark appearance keeps mobile rental-mode labels readable', async ({ page }) => {
  await openMobile(page, '/#/menu')
  await page.getByTestId('mobile-appearance-trigger').click()
  await page.locator('.m2-appearance-dialog [role="radio"]').nth(1).click()
  await page.goto('/#/')
  await expect(page.locator('html')).toHaveClass(/site-theme-dark/)

  const button = page.locator('.m2-mode-switch > button').first()
  await expect(button).toBeVisible()
  const colors = await button.evaluate((element) => {
    const label = element.querySelector('span:last-child')
    return {
      button: getComputedStyle(element).color,
      title: label ? getComputedStyle(label, '::before').color : '',
      subtitle: label ? getComputedStyle(label, '::after').color : '',
    }
  })
  expect(colors.button).toBe('rgb(242, 242, 242)')
  expect(colors.title).toBe('rgb(242, 242, 242)')
  expect(colors.subtitle).toBe('rgb(178, 178, 178)')
})

test('Spanish unknown listing facts are informational rather than CTA-like badges', async ({ page }) => {
  await openMobile(page, '/#/buscar?q=Tenerife')
  await page.evaluate(() => {
    const badges = document.createElement('div')
    badges.className = 'm2-result-card__badges'
    const unknown = document.createElement('span')
    unknown.dataset.testid = 'synthetic-spanish-unknown-fact'
    unknown.textContent = 'Consultar con el anunciante'
    badges.appendChild(unknown)
    document.body.appendChild(badges)
  })

  const unknown = page.getByTestId('synthetic-spanish-unknown-fact')
  await expect(unknown).toBeVisible()
  await expect(unknown).toHaveClass(/m2-unknown-fact/)
})

test('mobile filters remain within 320px viewport', async ({ page }) => {
  await openMobile(page, '/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
  expect(await page.locator('.m2-results-panel').evaluate((panel) => panel.scrollWidth <= panel.clientWidth)).toBe(true)
})
