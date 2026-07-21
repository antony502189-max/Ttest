import { expect, test, type Page } from '@playwright/test'

const mobile = { width: 390, height: 844 }

async function reset(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
}

test.beforeEach(async ({ page }) => {
  await reset(page)
})

test('DELTA-GEO-01 rejects external locations and keeps valid Tenerife catalog/history', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 })
  const input = page.getByPlaceholder('Municipio, barrio o zona de Tenerife').first()
  await input.fill('Madrid')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('En esta versión solo puedes buscar habitaciones en Tenerife.')
  await expect(page).toHaveURL(/#\/$/)

  await input.fill('santa cruz')
  await page.getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page).toHaveURL(/q=Santa\+Cruz\+de\+Tenerife/)
  await expect(page.getByRole('heading', { name: /habitaciones en Santa Cruz de Tenerife/i })).toBeVisible()

  await page.evaluate(() => localStorage.setItem('112233:search-history:v2', JSON.stringify({ version: 2, data: { guest: ['Madrid', 'Adeje', 'TENERIFE'] } })))
  await page.reload()
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:search-history:v2') || '{}').data.guest)).toEqual(['Adeje', 'Tenerife'])

  await page.goto('/#/buscar?q=Madrid')
  await expect(page.getByRole('alert')).toContainText('Solo buscamos en Tenerife')
  await expect(page.getByRole('heading', { name: /0 habitaciones en Tenerife/i })).toBeVisible()
})

test('DELTA-GEO-02 fullscreen location uses structured catalog, static market row and restores focus', async ({ page }) => {
  await page.setViewportSize(mobile)
  const trigger = page.getByRole('button', { name: /Abrir selección de ubicación/i }).first()
  await trigger.click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog).toHaveCSS('height', '844px')
  await expect(dialog.locator('.location-market-row button')).toHaveCount(0)
  await dialog.getByPlaceholder('Municipio, barrio, zona o dirección').fill('laguna')
  await expect(dialog.getByRole('button', { name: /San Cristóbal de La Laguna/i })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
})

test('DELTA-HOME-01 Para quién remains visible in both rental modes without height jump', async ({ page }) => {
  await page.setViewportSize(mobile)
  const panel = page.locator('.market-search-panel')
  const longHeight = (await panel.boundingBox())?.height
  await expect(page.getByRole('combobox', { name: 'Para quién' })).toBeVisible()
  await page.locator('.market-search-panel .rental-switch button').nth(1).click()
  await expect(page.getByRole('combobox', { name: 'Para quién' })).toBeVisible()
  const holidayHeight = (await panel.boundingBox())?.height
  expect(Math.abs((holidayHeight ?? 0) - (longHeight ?? 0))).toBeLessThanOrEqual(2)
  const locationRow = page.getByRole('button', { name: /Abrir selección de ubicación/i }).first()
  expect((await locationRow.boundingBox())?.width).toBeGreaterThan(300)
})

test('DELTA-MAP-01 draw action runs once in dedicated map and consumes its parameter', async ({ page }) => {
  await page.setViewportSize(mobile)
  await page.goto('/#/buscar?q=Tenerife&vista=mapa&dibujar=1')
  await expect(page.locator('.mobile-map-screen')).toBeVisible()
  await expect(page.locator('.leaflet-map-shell')).toHaveAttribute('data-drawing', 'true', { timeout: 15_000 })
  await expect(page.getByRole('status')).toContainText('Modo dibujo activado')
  await expect(page).not.toHaveURL(/dibujar=1/)
  await expect(page.locator('.site-header:visible, .mobile-header:visible, .bottom-nav:visible, .search-bar:visible')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Mostrar \d+ habitaciones/ })).toBeVisible()
  await page.reload()
  await expect(page.locator('.leaflet-map-shell')).not.toHaveAttribute('data-drawing', 'true')
})

test('DELTA-MAP-02 geolocation accepts Tenerife and rejects outside coordinates without repeated calls', async ({ page, context }) => {
  await context.grantPermissions(['geolocation'], { origin: 'http://127.0.0.1:4173' })
  await context.setGeolocation({ latitude: 28.2916, longitude: -16.6291 })
  await page.addInitScript(() => {
    let calls = 0
    Object.defineProperty(window, '__geoCalls', { get: () => calls })
    const original = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation)
    navigator.geolocation.getCurrentPosition = (...args) => { calls += 1; return original(...args) }
  })
  await page.reload()
  await page.setViewportSize(mobile)
  await page.goto('/#/buscar?q=Tenerife&vista=mapa&cerca=1')
  await expect(page.getByRole('status')).toContainText('Ubicación encontrada en Tenerife', { timeout: 15_000 })
  await expect(page).not.toHaveURL(/cerca=1/)
  await page.waitForTimeout(500)
  expect(await page.evaluate(() => (window as typeof window & { __geoCalls: number }).__geoCalls)).toBe(1)

  await context.setGeolocation({ latitude: 40.4168, longitude: -3.7038 })
  const outsidePage = await context.newPage()
  await outsidePage.setViewportSize(mobile)
  await outsidePage.goto('/#/buscar?q=Tenerife&vista=mapa&cerca=1')
  await expect(outsidePage.getByRole('status')).toContainText('fuera de Tenerife', { timeout: 15_000 })
  await expect(outsidePage.locator('.leaflet-map-canvas')).toBeVisible()
  await outsidePage.close()
})

test('DELTA-RESULTS-01 compact result cards and dedicated headers expose only intended controls', async ({ page }) => {
  await page.setViewportSize(mobile)
  await page.goto('/#/buscar?q=Tenerife')
  const top = page.locator('.mobile-results-topbar')
  const toolbar = page.locator('.idealista-results-toolbar')
  const firstCard = page.locator('.property-card').first()
  await expect(top).toBeVisible()
  await expect(toolbar).toBeVisible()
  expect((await firstCard.boundingBox())?.y).toBeLessThan(190)
  await expect(firstCard.getByRole('link', { name: 'Contactar' })).toBeVisible()
  const overflow = firstCard.getByRole('button', { name: /Más opciones para/i })
  await expect(overflow).toBeVisible()
  const overflowBox = await overflow.boundingBox()
  expect(overflowBox?.width).toBeGreaterThanOrEqual(43)
  await expect(overflow).not.toContainText('Más opciones')
})

test('DELTA-DETAIL-01 listing has icon bar, edge-to-edge gallery and non-overlapping contact/navigation', async ({ page }) => {
  await page.setViewportSize(mobile)
  await page.goto('/#/buscar?q=Tenerife')
  const href = await page.locator('.property-card h3 a').first().getAttribute('href')
  await page.goto(href ?? '/#/habitacion/room-1')
  const actionbar = page.locator('.listing-actionbar')
  await expect(actionbar.getByRole('link', { name: 'Volver al listado' })).toBeVisible()
  await expect(actionbar.getByRole('button', { name: 'Compartir' })).toBeVisible()
  await expect(actionbar.getByRole('button', { name: /Guardar|Guardado/ })).toBeVisible()
  await expect(actionbar.getByRole('button', { name: 'Más acciones del anuncio' })).toBeVisible()
  const gallery = await page.locator('.property-gallery').boundingBox()
  expect(gallery?.x).toBe(0)
  expect(gallery?.width).toBe(390)
  const contact = await page.locator('.mobile-contact-bar').boundingBox()
  const nav = await page.locator('.bottom-nav').boundingBox()
  expect(contact && nav && contact.y + contact.height <= nav.y + 1).toBeTruthy()
})

test('DELTA-LOCAL-01 local contact creates an honest user-scoped message row', async ({ page }) => {
  await page.setViewportSize(mobile)
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo')))
  await page.reload()
  await page.goto('/#/buscar?q=Tenerife')
  const href = await page.locator('.property-card h3 a').first().getAttribute('href')
  await page.goto(href ?? '/#/habitacion/room-1')
  await page.getByRole('button', { name: 'Enviar mensaje' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nombre').fill('Lucía')
  await dialog.getByLabel('Email o teléfono').fill('lucia@example.com')
  await dialog.getByLabel('Mensaje').fill('Hola, me interesa esta habitación en Tenerife.')
  await dialog.getByRole('checkbox').click()
  await page.waitForTimeout(750)
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('status')).toContainText('demo local')
  await page.goto('/#/mensajes')
  await expect(page.locator('.message-thread-row')).toHaveCount(1)
  await expect(page.locator('.message-thread-row')).toContainText('Demo local')
  await expect(page.locator('.message-thread-row')).toContainText('No enviado por internet')
})

test('DELTA-FILTER-01 Limpiar changes draft only until apply', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 })
  await page.goto('/#/buscar?q=Tenerife&precioMin=100')
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  const sheet = page.getByRole('dialog')
  await sheet.getByRole('button', { name: 'Limpiar' }).click()
  await expect(page).toHaveURL(/precioMin=100/)
  await expect(sheet).toBeVisible()
  await expect(sheet.locator('.range-values').first()).toContainText('0 €')
  await sheet.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()
  await expect(page).not.toHaveURL(/precioMin=100/)
})

test('DELTA-I18N-01 new mobile routes remain usable in ES, EN and RU', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  for (const language of ['es', 'en', 'ru']) {
    await page.evaluate((value) => localStorage.setItem('112233:language:v1', value), language)
    await page.goto('/#/buscar?q=Tenerife')
    await expect(page.locator('.mobile-results-topbar')).toBeVisible()
    await expect(page.locator('.bottom-nav')).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow, `${language} search should not overflow`).toBe(false)
  }
})

test('DELTA-RESPONSIVE-01 critical routes have no document overflow across required matrix', async ({ page }) => {
  test.setTimeout(150_000)
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  const sizes = [[320, 568], [360, 800], [375, 667], [390, 700], [390, 844], [412, 915], [667, 375], [844, 390], [768, 1024], [1024, 600], [1024, 768], [1440, 900]]
  for (const [width, height] of sizes) {
    await page.setViewportSize({ width, height })
    for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa', '/#/habitacion/arme%C3%B1ime-luminosa-01', '/#/menu', '/#/mensajes', '/#/perfil', '/#/publicar']) {
      await page.goto(route)
      const diagnostics = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
      expect(diagnostics.scroll, `${route} at ${width}x${height}`).toBeLessThanOrEqual(diagnostics.client)
    }
  }
})

test('DELTA-DIAGNOSTICS-01 critical routes emit no application errors or failed first-party requests', async ({ page }) => {
  test.setTimeout(90_000)
  const consoleErrors: string[] = []
  const pageErrors: string[] = []
  const failedFirstParty: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('requestfailed', (request) => { if (request.url().startsWith('http://127.0.0.1:4173')) failedFirstParty.push(`${request.method()} ${request.url()}`) })
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.evaluate(async () => { await document.fonts.ready })
  consoleErrors.length = 0
  pageErrors.length = 0
  failedFirstParty.length = 0
  for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/buscar?q=Tenerife&vista=mapa', '/#/habitacion/arme%C3%B1ime-luminosa-01', '/#/menu', '/#/mensajes', '/#/perfil', '/#/publicar']) {
    await page.goto(route)
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  }
  expect({ consoleErrors, pageErrors, failedFirstParty }).toEqual({ consoleErrors: [], pageErrors: [], failedFirstParty: [] })
})

test('DELTA-PAGES-01 HashRouter routes resolve after a direct document load', async ({ page }) => {
  for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/menu', '/#/mensajes']) {
    await page.goto(route)
    const response = await page.reload()
    expect(response?.ok()).toBe(true)
    await expect(page.locator('#root')).not.toBeEmpty()
    await expect(page.getByText('404', { exact: true })).toHaveCount(0)
  }
})
