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

async function loginMobileTenant(page: Page) {
  await page.goto('/#/acceso')
  const email = page.getByLabel(/^email$/i)
  if (!(await email.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
  }
  await email.fill('inquilina@112233.es')
  await page.locator('#login-password').or(page.getByLabel(/^contraseña$/i)).fill('demo112233')
  const desktopSubmit = page.getByRole('button', { name: /^acceder$/i })
  if (await desktopSubmit.isVisible().catch(() => false)) await desktopSubmit.click()
  else await page.getByRole('button', { name: /iniciar sesión con email/i }).click()
  await expect(page).not.toHaveURL(/acceso/)
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

test('mobile home keeps the original compact layout without extra pets or smoking controls', async ({ page }) => {
  await openMobile(page)
  await expect(page.getByTestId('mobile-home-pets-yes')).toHaveCount(0)
  await expect(page.getByTestId('mobile-home-smoking-yes')).toHaveCount(0)
  await expect(page.locator('.m2-home-extra-filters')).toHaveCount(0)
  await expect(page.getByTestId('open-location')).toBeVisible()
})

test('mobile Appearance row is removed and the app remains permanently light-only', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 })
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:appearance:v1', 'dark')
  })
  await page.goto('/#/menu')

  const root = page.locator('html')
  await expect(root).toHaveClass(/site-theme-light/)
  await expect(root).not.toHaveClass(/site-theme-dark/)
  await expect(root).toHaveAttribute('data-appearance', 'light')
  expect(await page.evaluate(() => localStorage.getItem('112233:appearance:v1'))).toBeNull()
  await expect(page.getByTestId('mobile-appearance-trigger')).toHaveCount(0)

  const appearanceRow = page.locator('.m2-menu-row').filter({ hasText: 'Apariencia' })
  await expect(appearanceRow).toBeHidden()
  await expect(page.locator('.m2-appearance-dialog')).toHaveCount(0)
  await expect(root).toHaveAttribute('data-appearance', 'light')
})

test('authenticated mobile account stays light even when the OS prefers dark', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await openMobile(page, '/#/acceso')
  await loginMobileTenant(page)
  await page.goto('/#/perfil')

  const root = page.locator('html')
  await expect(root).toHaveAttribute('data-appearance', 'light')
  await expect(root).toHaveClass(/site-theme-light/)
  await expect(root).not.toHaveClass(/site-theme-dark/)
  await expect(page.locator('.m2-account-screen')).toBeVisible()

  const surfaces = await page.locator('.m2-account-screen, .m2-account-content, .m2-account-form').evaluateAll((elements) => elements.map((element) => ({
    background: getComputedStyle(element).backgroundColor,
    color: getComputedStyle(element).color,
  })))
  expect(surfaces.length).toBeGreaterThanOrEqual(3)
  for (const surface of surfaces) {
    expect(surface.background).toBe('rgb(255, 255, 255)')
    expect(surface.color).toBe('rgb(37, 42, 43)')
  }

  const inputs = await page.locator('.m2-account-field input').evaluateAll((elements) => elements.map((element) => ({
    background: getComputedStyle(element).backgroundColor,
    color: getComputedStyle(element).color,
  })))
  expect(inputs.length).toBeGreaterThan(0)
  for (const input of inputs) {
    expect(input.background).toBe('rgb(255, 255, 255)')
    expect(input.color).toBe('rgb(37, 42, 43)')
  }
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
