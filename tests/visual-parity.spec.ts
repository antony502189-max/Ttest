import { expect, test, type Locator, type Page } from '@playwright/test'

async function settle(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
  await page.waitForTimeout(180)
}

async function open(page: Page, route: string, width = 390, height = 844) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await settle(page)
}

async function shot(page: Page, name: string, mask: Locator[] = []) {
  await expect(page).toHaveScreenshot(`${name}.png`, {
    animations: 'disabled',
    caret: 'hide',
    mask,
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.02,
  })
}

async function settleImages(page: Page, selector: string) {
  await page.locator(selector).first().waitFor({ state: 'attached' })
  await page.locator(selector).evaluateAll((images) => Promise.all(images.map((node) => {
    const image = node as HTMLImageElement
    if (image.complete) return Promise.resolve()
    return new Promise<void>((resolve) => { image.addEventListener('load', () => resolve(), { once: true }); image.addEventListener('error', () => resolve(), { once: true }) })
  })))
  await page.waitForTimeout(120)
}

async function setState(page: Page, state: { session?: string | null; language?: 'es' | 'en' | 'ru'; threads?: boolean }) {
  await page.goto('/#/')
  await page.evaluate(({ session, language, threads }) => {
    localStorage.setItem('112233:session:v1', JSON.stringify(session ?? null))
    if (language) localStorage.setItem('112233:language:v1', language)
    else localStorage.removeItem('112233:language:v1')
    if (threads) localStorage.setItem('112233:message-threads:v1', JSON.stringify({ version: 1, data: { 'tenant-demo': [{ id: 'visual-thread', listingId: 'armeñime-luminosa-01', listingTitle: 'Habitación luminosa con escritorio y gastos incluidos', imageRef: 'https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=82', contactName: 'Lucía', messagePreview: 'Hola, me interesa esta habitación.', createdAt: '2026-07-21T10:00:00.000Z', status: 'Demo local' }] } }))
  }, state)
  await page.reload()
}

test('home responsive visual matrix', async ({ page }) => {
  test.setTimeout(120_000)
  for (const [name, width, height] of [
    ['home-320x568', 320, 568],
    ['home-360x800', 360, 800],
    ['home-390x844', 390, 844],
    ['home-412x915', 412, 915],
    ['home-1440x900', 1440, 900],
  ] as const) {
    await open(page, '/#/', width, height)
    await shot(page, name, [page.locator('.promoted-listing img')])
  }
})

test('location, list, filters and sort visual states', async ({ page }) => {
  test.setTimeout(120_000)
  await open(page, '/#/')
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await shot(page, 'location-390x844')

  await open(page, '/#/buscar?q=Tenerife')
  await shot(page, 'search-list-390x844', [page.locator('.property-card__media img')])

  await open(page, '/#/buscar?q=Tenerife', 390, 700)
  await page.getByRole('button', { name: /Todos los filtros/i }).click()
  await expect(page.getByRole('heading', { name: 'Filtros' })).toBeVisible()
  await shot(page, 'filters-390x700')
  await page.keyboard.press('Escape')

  await open(page, '/#/buscar?q=Tenerife')
  await page.locator('.mobile-sort-control').click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await shot(page, 'sort-390x844')
})

test('dedicated map visual states', async ({ page }) => {
  test.setTimeout(120_000)
  await open(page, '/#/buscar?q=Tenerife&vista=mapa')
  await expect(page.locator('.mobile-map-screen')).toBeVisible()
  await shot(page, 'search-map-390x844', [page.locator('.leaflet-tile-pane')])

  await open(page, '/#/buscar?q=Tenerife&vista=mapa', 667, 375)
  await expect(page.locator('.mobile-map-screen')).toBeVisible()
  await shot(page, 'search-map-667x375', [page.locator('.leaflet-tile-pane')])
})

test('listing, gallery and contact visual states', async ({ page }) => {
  test.setTimeout(120_000)
  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01')
  await shot(page, 'listing-390x844', [page.locator('.property-gallery img')])

  await page.getByRole('button', { name: /Ver todas las fotos/i }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await settleImages(page, '.gallery-dialog__grid img')
  await shot(page, 'gallery-390x844', [page.getByRole('dialog').locator('img')])
  await page.keyboard.press('Escape')

  await open(page, '/#/habitacion/arme%C3%B1ime-luminosa-01')
  await page.getByRole('button', { name: 'Enviar mensaje' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await shot(page, 'contact-390x844')
})

test('menu, messages and profile visual states', async ({ page }) => {
  test.setTimeout(120_000)
  await open(page, '/#/menu')
  await shot(page, 'menu-390x844')

  await open(page, '/#/mensajes')
  await shot(page, 'messages-empty-390x844')

  await setState(page, { session: 'tenant-demo', threads: true })
  await open(page, '/#/mensajes')
  await shot(page, 'messages-filled-390x844', [page.locator('.message-thread-row img')])

  await setState(page, { session: 'host-demo' })
  await open(page, '/#/perfil')
  await shot(page, 'profile-390x844')
})

test('publish room, images and preview visual states', async ({ page }) => {
  test.setTimeout(180_000)
  await setState(page, { session: 'host-demo' })
  await open(page, '/#/publicar')
  const next = page.getByRole('button', { name: 'Continuar' })
  await next.click()
  await next.click()
  await shot(page, 'publish-room-390x844')

  for (let step = 0; step < 4; step += 1) await next.click()
  await shot(page, 'publish-images-390x844')

  for (let step = 0; step < 3; step += 1) await next.click()
  await shot(page, 'publish-preview-390x844', [page.locator('.preview-card-wrap img')])
})

test('Russian home and search visual states', async ({ page }) => {
  await setState(page, { language: 'ru' })
  await open(page, '/#/')
  await shot(page, 'home-ru-390x844', [page.locator('.promoted-listing img')])
  await open(page, '/#/buscar?q=Tenerife')
  await shot(page, 'search-ru-390x844', [page.locator('.property-card__media img')])
})
