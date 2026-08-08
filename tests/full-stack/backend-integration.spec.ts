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
  tenantRequirement,
  smokingAllowed: false,
  petsAllowed: false,
  childrenAllowed: false,
  empadronamientoAllowed: true,
  restrictions: ['No fumar'],
  amenities: ['Wifi'],
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

test('room count filter is executed by the backend and reflected in mobile results', async ({ page }) => {
  test.skip(test.info().project.name !== 'mobile-chromium', 'Mobile overlay is not rendered in the desktop project')
  const unique = `${Date.now()}-room-filter`
  await createBackendListing(unique, `Habitación cuatro cuartos ${unique}`)

  const failedResponses: string[] = []
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/') && response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`)
    }
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&habitaciones=4')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.locator('[data-listing-id]').first()).toBeVisible()
  expect(failedResponses).toEqual([])
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
  const removed = await api.delete(`${API_PREFIX}/listings/${created.listingId}`)
  expect(removed.status()).toBe(204)
  await api.dispose()

  // The provider also polls; focus gives the same version check immediately,
  // without requiring a page reload or changing the visible layout.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.getByText(title, { exact: true }).first()).not.toBeVisible()
})
