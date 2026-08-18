import { expect, test, type Page } from '@playwright/test'
import { isExpectedHeadlessVectorFallback } from './helpers/google-maps-console'

async function readyMobile(page: Page, route = '/#/') {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('DELTA-MOBILE-01 home, occupant selector and location actions stay connected without changing the locked design', async ({ page }) => {
  await readyMobile(page)
  await expect(page.locator('.m2-home')).toBeVisible()
  const modeButtons = page.locator('.m2-mode-switch > button')
  await expect(modeButtons).toHaveCount(2)
  const cardHeight = (await page.locator('.m2-search-card').boundingBox())?.height
  await modeButtons.last().click()
  expect(Math.abs(((await page.locator('.m2-search-card').boundingBox())?.height ?? 0) - (cardHeight ?? 0))).toBeLessThanOrEqual(2)

  await page.locator('.m2-occupant-trigger').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await page.locator('.m2-select-row').click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expect(page.locator('.m2-location-action')).toHaveCount(3)
  await expect(page).toHaveURL(/panel=ubicacion/)
})

test('DELTA-MOBILE-02 list, filters, sorting, map, back and reload are URL-backed', async ({ page }) => {
  await readyMobile(page, '/#/buscar?q=Tenerife&alquiler=long')
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await expect(results.locator('.m2-result-card')).not.toHaveCount(0)

  await results.getByRole('button', { name: 'Filtros' }).click()
  await expect(results.locator('.m2-results-filter')).toBeVisible()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await results.getByRole('button', { name: 'Orden' }).click()
  await results.getByRole('radio', { name: 'Más baratos' }).click()

  await results.getByRole('button', { name: 'Mapa' }).click()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page).toHaveURL(/vista=mapa/)
  await page.reload()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await page.getByRole('button', { name: 'Volver' }).click()
  await expect(page.getByTestId('location-screen')).toBeVisible()
})

test('DELTA-MOBILE-03 drawing and nearby search expose dedicated working map states', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:4173' })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
  await readyMobile(page, '/#/?panel=ubicacion')

  await page.getByTestId('draw-zone').click()
  await expect(page.getByTestId('map-draw')).toBeVisible()
  await page.getByRole('button', { name: 'Dibujar tu zona' }).click()
  await expect(page.getByTestId('freehand-overlay')).toBeVisible()
  await expect(page).toHaveURL(/vista=mapa.*dibujar=1/)
  await page.getByRole('button', { name: 'Cancelar dibujo' }).click()
  await page.getByRole('button', { name: 'Volver' }).click()

  await page.getByTestId('search-nearby').click()
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page).toHaveURL(/cerca=1.*lat=28\.2916.*lng=-16\.6291/)
})

test('DELTA-MOBILE-04 location never exposes the removed phone lookup', async ({ page }) => {
  await readyMobile(page, '/#/?panel=ubicacion')
  await expect(page.getByTestId('search-phone')).toHaveCount(0)
  await expect(page.getByTestId('phone-search-screen')).toHaveCount(0)
})

test('DELTA-MOBILE-05 bottom tabs, favorites and protected account actions are real routes', async ({ page }) => {
  await readyMobile(page, '/#/buscar?q=Tenerife')
  await page.locator('.m2-result-card__favorite').first().click()
  await expect(page.locator('[data-sonner-toast]').first()).toBeVisible()
  await page.getByRole('button', { name: 'Volver' }).click()
  await page.getByRole('button', { name: 'Favoritos', exact: true }).click()
  await expect(page).toHaveURL(/#\/favoritos/)
  await expect(page.locator('.m2-collection__list > button')).toHaveCount(1)

  await page.getByRole('button', { name: 'Menú', exact: true }).click()
  await expect(page).toHaveURL(/#\/menu/)
  await page.getByRole('button', { name: /Iniciar sesión/ }).click()
  await expect(page).toHaveURL(/#\/acceso/)
})

test('DELTA-MOBILE-06 ES, EN and RU persist and never introduce horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const language of ['es', 'en', 'ru'] as const) {
    await page.goto('/#/')
    await page.evaluate((value) => localStorage.setItem('112233:language:v1', value), language)
    await page.evaluate(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable'))
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('lang', language)
    await expect(page.locator('.m2-onboarding')).toBeVisible()
    const dimensions = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }))
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client)
  }
})

test('DELTA-RESPONSIVE-01 critical routes have no horizontal overflow across the supported matrix', async ({ page }) => {
  test.setTimeout(180_000)
  const sizes = [[320, 568], [360, 800], [390, 844], [412, 915], [768, 1024], [1024, 768], [1440, 900]]
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height })
    for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa', '/#/habitacion/arme%C3%B1ime-luminosa-01', '/#/menu']) {
      await page.goto(route)
      const dimensions = await page.evaluate(() => ({
        client: document.documentElement.clientWidth,
        scroll: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
      }))
      expect(dimensions.scroll, `${route} at ${width}x${height}`).toBeLessThanOrEqual(dimensions.client + 1)
    }
  }
})

test('DELTA-DIAGNOSTICS-01 critical mobile routes emit no application errors or failed first-party requests', async ({ page }) => {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  const failedFirstParty: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error' && !isExpectedHeadlessVectorFallback(message.text())) consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('requestfailed', (request) => {
    if (request.url().startsWith('http://127.0.0.1:4173')) failedFirstParty.push(`${request.method()} ${request.url()}`)
  })

  await readyMobile(page)
  consoleErrors.length = 0
  for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa', '/#/menu', '/#/mensajes']) {
    await page.goto(route)
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  }
  expect({ consoleErrors, pageErrors, failedFirstParty }).toEqual({ consoleErrors: [], pageErrors: [], failedFirstParty: [] })
})
