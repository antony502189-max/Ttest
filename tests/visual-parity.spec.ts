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
  await shot(page, 'current-location-390x844')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa')
  await expect(page.getByTestId('map-search')).toBeVisible()
  await shot(page, 'current-map-390x844')
})

test('current mobile menu, auth and Russian visual states', async ({ page }) => {
  await open(page, '/#/menu')
  await shot(page, 'current-menu-390x844')

  await open(page, '/#/acceso')
  await shot(page, 'current-auth-390x844')

  await page.evaluate(() => localStorage.setItem('112233:language:v1', 'ru'))
  await page.goto('/#/')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await shot(page, 'current-home-ru-390x844')
})

test('existing desktop results, listing and publication designs stay visually locked', async ({ page }) => {
  await open(page, '/#/buscar?q=Tenerife', 1440, 900)
  await shot(page, 'current-desktop-search-1440x900')

  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01', 1024, 900)
  await shot(page, 'current-listing-1024x900')

  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await open(page, '/#/publicar', 1024, 900)
  await shot(page, 'current-publish-1024x900')
})
