import { expectProvinceLocationVisual } from './helpers/province-location-visual'
import { expect, test, type Page } from '@playwright/test'

async function open(page: Page, route: string, width = 390, height = 844) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
}

async function shot(page: Page, name: string) {
  await expect(page).toHaveScreenshot(`${name}.png`, {
    animations: 'disabled',
    caret: 'hide',
    mask: [page.locator('.gm-style img[role="presentation"], .m2-result-card img, .property-card__media img, .property-gallery img')],
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.04,
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('current mobile home, results, location and map visual states', async ({ page }) => {
  await open(page, '/#/')
  await expect(page.locator('.m2-home')).toBeVisible()
  await shot(page, 'current-home-390x844')

  await open(page, '/#/buscar?q=Tenerife')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await shot(page, 'current-search-390x844')

  await page.getByRole('button', { name: 'Volver' }).click()
  await page.locator('.m2-select-row').click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expectProvinceLocationVisual(page)

  await open(page, '/#/buscar?q=Tenerife&vista=mapa')
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.locator('.m2-map-canvas')).toBeVisible({ timeout: 20_000 })
  await expect.poll(() => page.locator('.map-price-marker-shell, .map-cluster-marker-shell').count(), { timeout: 20_000 }).toBeGreaterThan(0)
  await shot(page, 'current-map-390x844')
})

test('current mobile menu, auth and Russian visual states', async ({ page }) => {
  await open(page, '/#/menu')
  const menu = page.getByTestId('mobile-menu')
  await expect(menu).toBeVisible()
  // The old menu PNG is intentionally NOT silently replaced: baseline approval
  // is owner-only (.github/workflows/update-visual-baselines.yml). Until that
  // approval, enforce the new customer-reference geometry, palette and card
  // order rather than asserting pixels against the superseded design.
  await expect(menu.getByTestId('menu-admin-entry')).toHaveCount(0)
  const visualMenu = await menu.evaluate((element) => {
    const header = element.querySelector(':scope > header')
    const account = element.querySelector('.m2-menu-account-card')
    const firstSection = element.querySelector('.m2-menu-section')
    const action = account?.querySelector('.m2-primary')
    const rows = Array.from(element.querySelectorAll('.m2-menu-group .m2-menu-row'))
    if (!header || !account || !firstSection || !action) throw new Error('Mobile menu structure missing')
    const a = account.getBoundingClientRect()
    const s = firstSection.getBoundingClientRect()
    return {
      headerBackground: getComputedStyle(header).backgroundColor,
      accountRadius: parseFloat(getComputedStyle(account).borderTopLeftRadius),
      actionRadius: parseFloat(getComputedStyle(action).borderTopLeftRadius),
      actionHeight: action.getBoundingClientRect().height,
      accountBeforePropertyRows: a.bottom < s.top,
      rowHeights: rows.map((row) => row.getBoundingClientRect().height),
      rowRadii: rows.map((row) => parseFloat(getComputedStyle(row).borderTopLeftRadius)),
      noOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
    }
  })
  expect(visualMenu.headerBackground).toBe('rgb(210, 255, 63)')
  expect(visualMenu.accountRadius).toBeGreaterThanOrEqual(12)
  expect(visualMenu.actionRadius).toBeGreaterThanOrEqual(24)
  expect(visualMenu.actionHeight).toBeGreaterThanOrEqual(60)
  expect(visualMenu.accountBeforePropertyRows).toBe(true)
  expect(visualMenu.rowHeights.length).toBeGreaterThanOrEqual(3)
  for (const height of visualMenu.rowHeights) expect(height).toBeGreaterThanOrEqual(60)
  for (const radius of visualMenu.rowRadii) expect(radius).toBeGreaterThanOrEqual(24)
  expect(visualMenu.noOverflow).toBe(true)

  await open(page, '/#/acceso')
  await shot(page, 'current-auth-390x844')

  const russianPage = await page.context().newPage()
  await russianPage.setViewportSize({ width: 390, height: 844 })
  await russianPage.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
  })
  await open(russianPage, '/#/')
  await russianPage.reload()
  await expect(russianPage.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(russianPage.getByText('Выберите язык приложения')).toBeVisible()
  await russianPage.getByRole('button', { name: 'Продолжить' }).click()
  await russianPage.getByRole('button', { name: 'Продолжить' }).click()
  await russianPage.getByRole('button', { name: 'Продолжить' }).click()
  await russianPage.getByRole('button', { name: 'Сейчас нет' }).click()
  await expect(russianPage.locator('.m2-home')).toBeVisible()
  await shot(russianPage, 'current-home-ru-390x844')
  await russianPage.close()
})

test('existing desktop results, listing and publication designs stay visually locked', async ({ page }) => {
  await open(page, '/#/buscar?q=Tenerife', 1440, 900)
  await shot(page, 'current-desktop-search-1440x900')

  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01', 1024, 900)
  await expect(page.locator('.idealista-listing-page')).toBeVisible()
  await expect(page.locator('.property-gallery')).toBeVisible()
  await expect(page.locator('.listing-title')).toBeVisible()
  await page.waitForLoadState('networkidle').catch(() => undefined)
  await shot(page, 'current-listing-1024x900')

  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await open(page, '/#/publicar', 1024, 900)
  await shot(page, 'current-publish-1024x900')
})
