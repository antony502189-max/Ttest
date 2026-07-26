import { expect, test, type BrowserContext, type Page } from '@playwright/test'

const origin = 'http://127.0.0.1:4173'

async function openLocation(page: Page) {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/?panel=ubicacion')
  await expect(page.getByTestId('location-screen')).toBeVisible()
}

async function allowTenerifeLocation(context: BrowserContext) {
  await context.grantPermissions(['geolocation'], { origin })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
}

test.describe('PR43 regression recovery', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('location keeps all four APK actions and phone lookup is reachable', async ({ page }) => {
    await openLocation(page)
    await expect(page.locator('.m2-location-action')).toHaveCount(4)
    await page.getByTestId('search-phone').click()
    await expect(page).toHaveURL(/panel=telefono/)
    await expect(page.getByTestId('phone-search-screen')).toBeVisible()
  })

  test('nearby success stores coordinates and radius in the URL', async ({ page, context }) => {
    await allowTenerifeLocation(context)
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page).toHaveURL(/cerca=1/)
    await expect(page).toHaveURL(/radio=30/)
    await expect(page).toHaveURL(/lat=28\.2916/)
    await expect(page).toHaveURL(/lng=-16\.6291/)
    await expect(page.getByTestId('map-search')).toBeVisible()
  })

  test('nearby rejects coordinates outside Tenerife without pretending success', async ({ page, context }) => {
    await context.grantPermissions(['geolocation'], { origin })
    await context.setGeolocation({ latitude: 40.4168, longitude: -3.7038 })
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('fuera de Tenerife')
    await expect(page).toHaveURL(/panel=ubicacion/)
  })

  test('nearby handles denied permission', async ({ page, context }) => {
    await context.clearPermissions()
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('No has permitido')
    await expect(page).toHaveURL(/panel=ubicacion/)
  })

  for (const failure of [
    { code: 2, text: 'no está disponible', name: 'unavailable' },
    { code: 3, text: 'tardado demasiado', name: 'timeout' },
  ]) {
    test(`nearby handles ${failure.name}`, async ({ page }) => {
      await page.addInitScript((code) => {
        Object.defineProperty(navigator, 'geolocation', {
          configurable: true,
          value: {
            getCurrentPosition: (_success: PositionCallback, error: PositionErrorCallback) => error({
              code,
              message: 'mock failure',
              PERMISSION_DENIED: 1,
              POSITION_UNAVAILABLE: 2,
              TIMEOUT: 3,
            } as GeolocationPositionError),
          },
        })
      }, failure.code)
      await openLocation(page)
      await page.getByTestId('search-nearby').click()
      await expect(page.getByRole('alert')).toContainText(failure.text)
    })
  }

  test('nearby handles an unavailable Geolocation API', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined })
    })
    await openLocation(page)
    await page.getByTestId('search-nearby').click()
    await expect(page.getByRole('alert')).toContainText('no ofrece geolocalización')
  })

  test('polygon exposes Search this area and survives map-list-reload', async ({ page }) => {
    const polygon = '28.00000,-16.79000;28.00000,-16.50000;28.17000,-16.50000;28.17000,-16.79000'
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&dibujar=1&poligono=${encodeURIComponent(polygon)}`)

    const searchArea = page.getByTestId('search-this-area')
    await expect(searchArea).toBeVisible()
    await searchArea.click()
    await expect(page).toHaveURL(/vista=mapa/)
    await expect(page).not.toHaveURL(/dibujar=1/)
    await expect(page).toHaveURL(/poligono=/)

    await page.getByRole('button', { name: 'Listado' }).click()
    const cards = page.locator('.m2-result-card')
    await expect.poll(() => cards.count()).toBeGreaterThan(0)
    const beforeReload = await cards.count()
    expect(beforeReload).toBeLessThan(23)
    await page.reload()
    await expect(cards).toHaveCount(beforeReload)
    await expect(page).toHaveURL(/poligono=/)
  })
})
