import { expect, request as playwrightRequest, test } from '@playwright/test'

const API = 'http://127.0.0.1:8000'
const API_PREFIX = '/api/v1'
let nextTestClient = 1

function testClientIp() {
  // The full-stack backend is shared by the desktop and mobile Playwright
  // projects.  Use distinct documentation-only client addresses for their
  // direct API fixtures so the real per-client verification-code limit does
  // not leak from one independent fixture into another.
  return `192.0.2.${nextTestClient++}`
}

const listingPayload = (title: string, tenantRequirement: 'any' | 'single-man' = 'any') => ({
  title,
  city: 'Santa Cruz de Tenerife',
  area: 'Centro',
  street: 'Private street',
  postcode: '38001',
  approximateAddress: 'Centro · ubicación aproximada',
  rentalMode: 'long',
  monthlyPrice: 725,
  nightlyPrice: null,
  weeklyPrice: null,
  roomType: 'Habitación individual',
  availableFrom: new Date().toISOString().slice(0, 10),
  availableUntil: null,
  minimumStayMonths: 1,
  minimumNights: null,
  depositAmount: 725,
  billsIncluded: true,
  bathroom: 'Baño compartido',
  kitchen: 'Cocina compartida',
  furnished: true,
  roomSizeM2: 16,
  bedroomCount: 4,
  currentResidents: 2,
  roomCapacity: 1,
  shower: 'Ducha compartida',
  homeSizeM2: 82,
  bathroomCount: 2,
  rentalUnit: 'room',
  bedType: 'double',
  bedCount: 1,
  currentRoomResidents: 0,
  toilet: 'Aseo privado',
  householdGender: 'mixed',
  householdHasChildren: false,
  heatingType: 'none',
  accessible: true,
  floor: 'top',
  couplesAllowed: true,
  acceptedTenantTypes: ['man', 'woman', 'couple'],
  tenantRequirement,
  smokingAllowed: false,
  petsAllowed: false,
  childrenAllowed: false,
  empadronamientoAllowed: true,
  restrictions: ['No fumar'],
  amenities: ['Wifi', 'Aire acondicionado', 'Jardín'],
  latitude: 28.4636,
  longitude: -16.2518,
  exactLatitude: 28.464,
  exactLongitude: -16.2514,
  description: 'Anuncio creado por la prueba full-stack para comprobar la integración real.',
  homeDescription: 'Respeta las zonas comunes.',
  advertiserType: 'Particular',
  source: 'playwright-full-stack',
  expiresAt: new Date(Date.now() + 60 * 86_400_000).toISOString(),
})

const paginationListing = (index: number) => ({
  id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
  ownerUserId: '00000000-0000-4000-8000-000000000001',
  owner: { name: 'Pagination Host', initials: 'PH', since: '2026-01-01T00:00:00Z', response: 'Consulta disponibilidad', verified: true },
  contactPhone: null, contactWhatsapp: null, contactEmail: null,
  showPhone: false, showWhatsApp: false,
  coverImageUrl: null, imageUrls: [],
  title: `Pagination listing ${index}`,
  city: 'Santa Cruz de Tenerife', area: 'Centro', approximateAddress: 'Centro',
  price: 600 + index, cadence: 'mes', monthlyPrice: 600 + index, nightlyPrice: null, weeklyPrice: null,
  rentalMode: 'long', roomType: 'Habitación individual',
  availableFrom: '2026-01-01', availableUntil: null, minimumStayMonths: 1, minimumNights: null,
  depositAmount: 0, depositText: null, billsIncluded: true, billsText: null,
  bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, roomSizeM2: 12,
  bedroomCount: 3, currentResidents: 2, roomCapacity: 1, shower: 'Ducha compartida',
  tenantRequirement: 'any', smokingAllowed: false, petsAllowed: false, childrenAllowed: false,
  empadronamientoAllowed: false, restrictions: [], amenities: [], status: 'published',
  latitude: 28.4636, longitude: -16.2518,
  description: 'Controlled multi-page API client regression fixture.', homeDescription: 'Shared home.',
  advertiserName: null, advertiserType: 'Particular', source: null,
  isExternal: false, primarySource: null, sourceUrl: null, sourcePriceText: null,
  priceCurrency: null, pricePeriod: null, priceIsFrom: null,
  publishedAt: '2026-01-01T00:00:00Z', expiresAt: '2099-01-01T00:00:00Z', views: 0, closedReason: null,
})

async function createBackendListing(unique: string, title: string, tenantRequirement: 'any' | 'single-man' = 'any') {
  const api = await playwrightRequest.newContext({
    baseURL: API,
    extraHTTPHeaders: {
      Origin: 'http://127.0.0.1:4174',
      'X-Real-IP': testClientIp(),
    },
  })
  const registration = await api.post(`${API_PREFIX}/auth/register`, {
    data: {
      name: 'Full Stack Host',
      email: `host-${unique}@example.com`,
      password: 'Correct-Horse-1234',
      role: 'host',
    },
  })
  expect(registration.status()).toBe(201)
  const session = await registration.json() as { accessToken: string }
  const verification = await api.post(`${API_PREFIX}/auth/email-verification/request`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  })
  expect(verification.status()).toBe(202)
  const { verificationCode } = await verification.json() as { verificationCode: string }
  expect(verificationCode).toMatch(/^\d{6}$/)
  const confirmed = await api.post(`${API_PREFIX}/auth/email-verification/confirm`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: { code: verificationCode },
  })
  expect(confirmed.status()).toBe(204)
  const created = await api.post(`${API_PREFIX}/listings`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: listingPayload(title, tenantRequirement),
  })
  expect(created.status()).toBe(201)
  const listing = await created.json() as { id: string }
  await api.dispose()
  return { listingId: listing.id, accessToken: session.accessToken }
}

test('frontend renders a listing created through the real FastAPI backend', async ({ page }) => {
  const unique = `${Date.now()}-${test.info().project.name}`
  const title = `Habitación full-stack ${unique}`
  await createBackendListing(unique, title)

  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByText(title, { exact: true }).first()).toBeVisible()
  expect(consoleErrors).toEqual([])
})

test('customer-priority fields persist through FastAPI, search uses them, and private location stays owner-only', async () => {
  const unique = `${Date.now()}-customer-sync-${test.info().project.name}`
  const title = `Habitación customer sync ${unique}`
  const created = await createBackendListing(unique, title)
  const api = await playwrightRequest.newContext({
    baseURL: API,
    extraHTTPHeaders: {
      Origin: 'http://127.0.0.1:4174',
      Authorization: `Bearer ${created.accessToken}`,
      'X-Real-IP': testClientIp(),
    },
  })

  const mineResponse = await api.get(`${API_PREFIX}/listings/mine`)
  expect(mineResponse.status()).toBe(200)
  const mine = await mineResponse.json() as Array<Record<string, unknown>>
  const owned = mine.find((item) => item.id === created.listingId)
  expect(owned).toBeTruthy()
  expect(owned).toMatchObject({
    id: created.listingId,
    floor: 'top',
    toilet: 'Aseo privado',
    bedType: 'double',
    accessible: true,
    street: 'Private street',
    postcode: '38001',
    exactLatitude: 28.464,
    exactLongitude: -16.2514,
  })

  const searchResponse = await api.post(`${API_PREFIX}/listings/search`, {
    data: {
      rentalMode: 'long',
      floor: 'top',
      amenities: ['Aire acondicionado', 'Jardín'],
      availableUntil: '2030-01-01',
      limit: 100,
      offset: 0,
    },
  })
  expect(searchResponse.status()).toBe(200)
  const search = await searchResponse.json() as { items: Array<Record<string, unknown>> }
  const publicListing = search.items.find((item) => item.id === created.listingId)
  expect(publicListing).toBeTruthy()
  expect(publicListing).toMatchObject({ id: created.listingId, floor: 'top', latitude: 28.4636, longitude: -16.2518 })
  expect(publicListing).not.toHaveProperty('street')
  expect(publicListing).not.toHaveProperty('postcode')
  expect(publicListing).not.toHaveProperty('exactLatitude')
  expect(publicListing).not.toHaveProperty('exactLongitude')

  const wrongFloorResponse = await api.post(`${API_PREFIX}/listings/search`, {
    data: { rentalMode: 'long', floor: '1', limit: 100, offset: 0 },
  })
  expect(wrongFloorResponse.status()).toBe(200)
  const wrongFloor = await wrongFloorResponse.json() as { items: Array<{ id: string }> }
  expect(wrongFloor.items.some((item) => item.id === created.listingId)).toBe(false)
  await api.dispose()
})

test('unrestricted search does not send a strict tenant requirement to the API', async ({ page }) => {
  const unique = `${Date.now()}-${test.info().project.name}`
  const unrestrictedTitle = `HabitaciГіn unrestricted ${unique}`
  const restrictedTitle = `HabitaciГіn tenant-metadata ${unique}`
  await createBackendListing(unique, unrestrictedTitle, 'any')
  await createBackendListing(`${unique}-second`, restrictedTitle, 'single-man')

  await page.goto('/#/buscar?q=Tenerife&alquiler=long&requisito=any')
  await expect(page.getByText(unrestrictedTitle, { exact: true }).first()).toBeVisible()
  await expect(page.getByText(restrictedTitle, { exact: true }).first()).toBeVisible()
})

test('unrestricted tourism search omits default price and room-size bounds from the real API request', async ({ page }) => {
  test.skip(test.info().project.name !== 'desktop-chromium', 'The responsive mobile control is covered by the mobile suite; this request-payload regression exercises the visible desktop mode control.')
  const searches: Record<string, unknown>[] = []
  page.on('request', (request) => {
    if (request.method() !== 'POST' || !request.url().includes('/api/v1/listings/search')) return
    const body = request.postData()
    if (!body) return
    const parsed = JSON.parse(body) as Record<string, unknown>
    if (parsed.rentalMode === 'holiday') searches.push(parsed)
  })

  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  // Exercise the real mode control instead of depending on the direct
  // holiday-route mount timing in the mobile project.
  await page.getByRole('radio', { name: /Turismo/ }).click()
  await expect.poll(() => searches.length).toBeGreaterThan(0)

  const body = searches[0]
  expect(body).toMatchObject({ rentalMode: 'holiday', query: 'Tenerife' })
  expect(body).not.toHaveProperty('minPrice')
  expect(body).not.toHaveProperty('maxPrice')
  expect(body).not.toHaveProperty('minRoomSizeM2')
  expect(body).not.toHaveProperty('maxRoomSizeM2')

  await page.getByRole('button', { name: /Todos los filtros/ }).click()
  const drawer = page.locator('.filter-drawer')
  await expect(drawer.getByLabel('Precio mínimo')).toHaveValue('0')
  await expect(drawer.getByLabel('Precio máximo')).toHaveValue('350')
  await expect(drawer.getByLabel('Precio máximo')).toHaveAttribute('max', '350')
})

test('browser catalog client requests every API page after the 100-record boundary', async ({ page }) => {
  const catalog = Array.from({ length: 150 }, (_, index) => paginationListing(index))
  const offsets: number[] = []
  await page.route('**/api/v1/listings/search', async (route) => {
    const request = route.request().postDataJSON() as { limit?: number; offset?: number }
    const offset = request.offset ?? 0
    offsets.push(offset)
    await route.fulfill({
      json: {
        items: catalog.slice(offset, offset + (request.limit ?? 100)),
        total: catalog.length,
        limit: request.limit ?? 100,
        offset,
      },
    })
  })

  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByText('Pagination listing 0', { exact: true }).first()).toBeVisible()
  // The catalog refresh effect may legitimately repeat a completed request
  // during a React update.  Verify that both required pages were requested
  // without turning that harmless duplicate into a flaky failure.
  await expect.poll(() => [...new Set(offsets)].sort((left, right) => left - right)).toEqual([0, 100])
})

test('anonymous auth and publication routes render without a route error', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))

  await page.goto('/#/acceso')
  await expect(page.locator('.m2-auth-screen')).toBeVisible()
  await expect(page.locator('.route-error')).toHaveCount(0)

  await page.goto('/#/publicar')
  await expect(page).toHaveURL(/#\/acceso$/)
  await expect(page.locator('.m2-auth-screen')).toBeVisible()
  await expect(page.locator('.route-error')).toHaveCount(0)
  expect(consoleErrors).toEqual([])
})

test('legacy bedroom-count URL parameter is removed from customer search', async ({ page }) => {
  test.skip(test.info().project.name !== 'mobile-chromium', 'Mobile overlay is not rendered in the desktop project')
  const requests: Record<string, unknown>[] = []
  page.on('request', (request) => {
    if (request.url().includes('/listings/search') && request.method() === 'POST') requests.push(request.postDataJSON() as Record<string, unknown>)
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&habitaciones=4')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page).not.toHaveURL(/habitaciones=/)
  expect(requests.some((body) => 'bedroomCounts' in body)).toBe(false)
})

test('an open catalog refreshes after its version changes on focus', async ({ page }) => {
  const unique = `${Date.now()}-catalog-version`
  const title = `HabitaciГіn catalog ${unique}`
  const created = await createBackendListing(unique, title)

  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByText(title, { exact: true }).first()).toBeVisible()

  const api = await playwrightRequest.newContext({
    baseURL: API,
    extraHTTPHeaders: { Origin: 'http://127.0.0.1:4174', Authorization: `Bearer ${created.accessToken}` },
  })
  const closed = await api.patch(`${API_PREFIX}/listings/${created.listingId}`, {
    data: { status: "closed" },
  })
  expect(closed.status()).toBe(200)
  await api.dispose()

  // The provider also polls; focus gives the same version check immediately,
  // without requiring a page reload or changing the visible layout.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.getByText(title, { exact: true }).first()).not.toBeVisible()
})
