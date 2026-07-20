import { expect, test, type Page } from '@playwright/test'

const hostSession = 'host-demo'
const firstListingId = 'armeñime-luminosa-01'
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n1cAAAAASUVORK5CYII=', 'base64')

async function clearLocalState(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

async function openAs(page: Page, userId: string, path: string) {
  await page.goto('/#/')
  await page.evaluate((id) => localStorage.setItem('112233:session:v1', JSON.stringify(id)), userId)
  await page.reload()
  await page.goto(path)
}

async function storedListings(page: Page) {
  return page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}') as { data: Array<Record<string, any>> }
    return payload.data
  })
}

async function resultCount(page: Page) {
  return Number.parseInt((await page.locator('#results-title').innerText()).replace(/\D/g, ''))
}

async function continueWizard(page: Page, count: number) {
  for (let index = 0; index < count; index += 1) await page.getByRole('button', { name: 'Continuar' }).click()
}

test.beforeEach(async ({ page }) => clearLocalState(page))

test('USR-03..05 history, discarded listings and guest data stay in separate scopes', async ({ page }) => {
  await page.getByLabel('Ciudad, barrio o zona').fill('Arona')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page).toHaveURL(/q=Arona/)
  const guestCard = page.locator('.results-list .property-card').first()
  await expect(guestCard).toContainText('Arona')
  const guestDiscardedId = await guestCard.getAttribute('data-listing-id')
  await guestCard.getByRole('button', { name: 'Más opciones' }).click()
  await page.getByRole('menuitem', { name: 'Descartar' }).click()

  const guestScopes = await page.evaluate(() => ({
    history: JSON.parse(localStorage.getItem('112233:search-history:v2') ?? '{}').data,
    discarded: JSON.parse(localStorage.getItem('112233:discarded:v2') ?? '{}').data,
  }))
  expect(guestScopes.history.guest).toContain('Arona')
  expect(guestScopes.discarded.guest).toContain(guestDiscardedId)

  await openAs(page, 'tenant-demo', '/#/buscar?q=Arona&alquiler=long')
  await expect(page.locator(`[data-listing-id="${guestDiscardedId}"]`)).toBeVisible()
  await page.getByLabel('Ciudad, barrio o zona').fill('Adeje')
  await page.getByRole('button', { name: 'Buscar' }).click()
  await expect(page).toHaveURL(/q=Adeje/)
  const tenantCard = page.locator('.results-list .property-card').first()
  await expect(tenantCard).toContainText('Adeje')
  const tenantDiscardedId = await tenantCard.getAttribute('data-listing-id')
  await tenantCard.getByRole('button', { name: 'Más opciones' }).click()
  await page.getByRole('menuitem', { name: 'Descartar' }).click()

  const scoped = await page.evaluate(() => ({
    history: JSON.parse(localStorage.getItem('112233:search-history:v2') ?? '{}').data,
    discarded: JSON.parse(localStorage.getItem('112233:discarded:v2') ?? '{}').data,
  }))
  expect(scoped.history.guest).toContain('Arona')
  expect(scoped.history['tenant-demo']).toContain('Adeje')
  expect(scoped.discarded.guest).toContain(guestDiscardedId)
  expect(scoped.discarded['tenant-demo']).toContain(tenantDiscardedId)
  expect(scoped.discarded['tenant-demo']).not.toContain(guestDiscardedId)

  await openAs(page, hostSession, '/#/buscar?q=Adeje&alquiler=long')
  await expect(page.locator(`[data-listing-id="${tenantDiscardedId}"]`)).toBeVisible()
})

test('STORE-05 validator rejects incomplete listing payloads instead of accepting corrupted data', async ({ page }) => {
  await page.evaluate(() => localStorage.setItem('112233:listings:v3', JSON.stringify({
    version: 3,
    data: [{ id: 'broken', title: 'Incomplete', rentalMode: 'long', images: [], publishedAt: '2026-07-20' }],
  })))
  await page.reload()
  await expect(page.getByRole('alert').filter({ hasText: /datos locales dañados/ })).toBeVisible()
  await expect.poll(() => storedListings(page).then((items) => items.length)).toBe(32)
})

test('MEDIA-05..07 exact MIME, IndexedDB quota feedback and missing-blob fallback work', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await continueWizard(page, 6)
  await page.locator('#publish-images').setInputFiles({ name: 'room.gif', mimeType: 'image/gif', buffer: Buffer.from('GIF89a') })
  await expect(page.locator('.image-uploader').getByRole('status')).toContainText('JPEG, PNG o WebP')

  await page.evaluate(() => {
    Object.defineProperty(IDBObjectStore.prototype, 'put', {
      configurable: true,
      value() { throw new DOMException('quota', 'QuotaExceededError') },
    })
  })
  await page.locator('#publish-images').setInputFiles({ name: 'room.png', mimeType: 'image/png', buffer: png })
  await expect(page.locator('.image-uploader').getByRole('status')).toContainText('espacio suficiente')

  await page.evaluate((id) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}') as { data: Array<Record<string, unknown>> }
    payload.data = payload.data.map((item) => item.id === id ? { ...item, images: ['idb-media:missing'] } : item)
    localStorage.setItem('112233:listings:v3', JSON.stringify({ version: 3, data: payload.data }))
  }, firstListingId)
  await page.reload()
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await expect(page.locator('.property-gallery img').first()).toHaveAttribute('src', /^data:image\/svg/)
})

test('ROOM-01..04 MODE-01..03 holiday wizard values persist and all new filters affect results', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await page.getByRole('radio', { name: 'Alquiler vacacional' }).click()
  await continueWizard(page, 2)
  await page.getByLabel('Tamaño aproximado').fill('19')
  await page.getByLabel('Personas que viven en casa').fill('3')
  await page.getByLabel('Ducha').selectOption('Ducha privada')
  await page.getByText('Lavadora', { exact: true }).click()
  await continueWizard(page, 1)
  await page.getByLabel('Precio por noche').fill('61')
  await page.getByLabel('Precio por semana').fill('360')
  await page.getByLabel('Precio por mes').fill('1200')
  await continueWizard(page, 1)
  await page.getByLabel('Estancia mínima (noches)').fill('4')
  await page.getByLabel('Disponible hasta').fill('2026-12-31')
  await continueWizard(page, 1)
  await page.getByLabel('Requisito para la persona inquilina').selectOption('couple')
  await continueWizard(page, 4)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText(/ya está visible/)).toBeVisible()

  const listing = (await storedListings(page))[0]
  expect(listing).toMatchObject({
    rentalMode: 'holiday', roomSizeM2: 19, currentResidents: 3, roomCapacity: 2,
    shower: 'Ducha privada', tenantRequirement: 'couple', couplesAllowed: true,
    nightlyPrice: 61, weeklyPrice: 360, monthlyPrice: 1200,
    minimumNights: 4, availableUntil: '2026-12-31',
  })
  expect(listing.genderPreference).toBe('Sin preferencia de género')
  expect(listing.amenities.filter((item: string) => item === 'Lavadora')).toHaveLength(1)

  const query = '/#/buscar?alquiler=holiday&tamanoMin=19&tamanoMax=19&ducha=Ducha%20privada&residentes=3&capacidad=2&nochesMin=4&hasta=2026-12-31'
  await page.goto(query)
  await expect(page.locator(`[data-listing-id="${listing.id}"]`)).toBeVisible()
  await expect(page.locator(`[data-listing-id="${listing.id}"]`)).toContainText('/noche')
  await page.goto(`/#/habitacion/${encodeURIComponent(String(listing.id))}`)
  await expect(page.locator('.detail-list')).toContainText('Semana')
  await expect(page.locator('.detail-list')).toContainText('360 €')
  await expect(page.locator('.detail-list')).toContainText('1200 €')
  await expect(page.getByText('Lavadora', { exact: true })).toHaveCount(1)
  await page.goto('/#/buscar?alquiler=long')
  await expect(page.locator('.property-card').first()).toContainText('/mes')
})

test('LOC-01 selected zone coordinates persist, edit restores them and exact street stays private', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await continueWizard(page, 1)
  await page.getByLabel('Zona o barrio').fill('El Médano')
  await page.getByLabel('Calle').fill('Calle Secreta 99')
  await expect(page.getByText(/Coordenadas aproximadas: 28\.0477, -16\.5363/)).toBeVisible()
  await page.getByRole('button', { name: 'Mover punto al este' }).click()
  await continueWizard(page, 8)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  const listing = (await storedListings(page))[0]
  expect(listing.area).toBe('El Médano')
  expect(listing.coordinates.lat).toBeCloseTo(28.0477, 4)
  expect(listing.coordinates.lng).toBeCloseTo(-16.5343, 4)
  await page.goto(`/#/habitacion/${encodeURIComponent(String(listing.id))}`)
  await expect(page.locator('main')).not.toContainText('Calle Secreta 99')
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(String(listing.id))}/editar`)
  await continueWizard(page, 1)
  await expect(page.getByText(/Coordenadas aproximadas: 28\.0477, -16\.5343/)).toBeVisible()
})

test('PROFILE-02 publish defaults and preview expose only enabled contact methods', async ({ page }) => {
  await openAs(page, hostSession, '/#/perfil')
  await page.getByRole('button', { name: 'Editar perfil' }).click()
  await page.getByRole('switch', { name: /Mostrar teléfono/ }).click()
  await page.getByRole('switch', { name: /Permitir WhatsApp/ }).click()
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await page.goto('/#/publicar')
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}').data)).toMatchObject({
    showPhone: false, showWhatsApp: false, allowContactForm: true,
    contactPhone: '+34 600 112 233', contactWhatsapp: '+34 611 223 344',
  })
  await continueWizard(page, 8)
  await expect(page.getByRole('checkbox', { name: /Mostrar teléfono/ })).not.toBeChecked()
  await expect(page.getByRole('checkbox', { name: /Permitir WhatsApp/ })).not.toBeChecked()
  await page.getByRole('checkbox', { name: /Permitir mensaje local/ }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByRole('alert')).toContainText('Activa al menos una forma de contacto')
  await page.getByRole('checkbox', { name: /Permitir mensaje local/ }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  const methods = page.locator('.preview-contact-methods').first()
  await expect(methods).toContainText('Mensaje local')
  await expect(methods).not.toContainText('Teléfono')
  await expect(methods).not.toContainText('WhatsApp')
})

test('FILTER-02..06 new filters have chips, reset, reload and history navigation', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByLabel('Estancia mínima aceptada')).toBeVisible()
  const baseline = await resultCount(page)
  const sidebar = page.locator('.filter-sidebar')
  await sidebar.getByLabel('Tamaño mínimo (m²)').fill('18')
  await expect(page).toHaveURL(/tamanoMin=18/)
  await expect.poll(() => resultCount(page)).toBeLessThan(baseline)
  await sidebar.getByLabel('Ducha').selectOption('Ducha privada')
  await sidebar.getByLabel('Residentes actuales (exacto)').selectOption('1')
  await sidebar.getByLabel('Capacidad de la habitación').selectOption('1')
  await expect(page).toHaveURL(/ducha=Ducha/)
  await expect(page).toHaveURL(/residentes=1/)
  await expect(page).toHaveURL(/capacidad=1/)
  await expect(page.locator('.applied-filters')).toContainText('18–50 m²')
  await expect(page.locator('.applied-filters')).toContainText('Ducha')
  const filtered = await resultCount(page)
  await page.reload()
  await expect.poll(() => resultCount(page)).toBe(filtered)
  const capacityOneUrl = page.url()
  await page.goto(capacityOneUrl.replace('capacidad=1', 'capacidad=2'))
  await expect(page).toHaveURL(/capacidad=2/)
  await page.goBack()
  await expect(sidebar.getByLabel('Capacidad de la habitación')).toHaveValue('1')
  await page.goForward()
  await expect(sidebar.getByLabel('Capacidad de la habitación')).toHaveValue('2')
  await page.locator('.applied-filters__clear').click()
  await expect(page).not.toHaveURL(/tamanoMin|ducha|residentes|capacidad/)

  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await sidebar.getByLabel('Máximo de noches mínimas').fill('4')
  await sidebar.getByLabel('Disponible hasta al menos').fill('2026-11-01')
  await expect(page).toHaveURL(/nochesMin=4/)
  await expect(page).toHaveURL(/hasta=2026-11-01/)
  await expect(page.locator('.applied-filters')).toContainText('4 noches')
})

test('MAP-04 visible-area state activates after movement and resets after search', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await page.locator('.leaflet-map-canvas').waitFor({ state: 'visible' })
  const searchArea = page.getByRole('button', { name: 'Buscar en esta zona' })
  await expect(searchArea).not.toHaveAttribute('data-dirty')
  await page.locator('.leaflet-control-zoom-in').click()
  await expect(searchArea).toHaveAttribute('data-dirty', 'true')
  await searchArea.click()
  await expect(searchArea).not.toHaveAttribute('data-dirty')
})

test('MAP-05 tile errors expose the existing accessible map error state', async ({ page }) => {
  await page.route('**tile.openstreetmap.org/**', (route) => route.abort())
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(page.getByRole('alert').filter({ hasText: 'No se pudo cargar el mapa' })).toBeVisible()
  await expect(page.getByLabel('Alternativa textual al mapa')).toBeVisible()
})

test('WIZ-04 reset clears dirty state and short-height filter drawer remains usable', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await page.getByRole('radio', { name: 'Alquiler vacacional' }).click()
  await expect(page.locator('.dirty-state')).toHaveText('Cambios sin guardar')
  await page.getByRole('button', { name: 'Restablecer' }).click()
  const resetDialog = page.getByRole('alertdialog', { name: '¿Restablecer el borrador?' })
  await resetDialog.getByRole('button', { name: 'Restablecer' }).click()
  await expect(page.locator('.dirty-state')).toHaveText('Borrador guardado')

  await page.setViewportSize({ width: 390, height: 560 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.locator('.mobile-filter-control button').click()
  const drawer = page.locator('.filter-drawer')
  const box = await drawer.boundingBox()
  expect(box && box.y >= 0 && box.y + box.height <= 561).toBeTruthy()
  await expect(drawer.locator('.filter-footer')).toBeVisible()
})
