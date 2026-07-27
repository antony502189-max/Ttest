import { expect, request as playwrightRequest, test } from '@playwright/test'

const API = 'http://127.0.0.1:8000/api/v1'

const listingPayload = (title: string) => ({
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
  tenantRequirement: 'any',
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

test('frontend renders a listing created through the real FastAPI backend', async ({ page }) => {
  const unique = `${Date.now()}-${test.info().project.name}`
  const title = `Habitación full-stack ${unique}`
  const api = await playwrightRequest.newContext({ baseURL: API, extraHTTPHeaders: { Origin: 'http://127.0.0.1:4174' } })
  const registration = await api.post('/auth/register', {
    data: { name: 'Full Stack Host', email: `host-${unique}@example.test`, password: 'Correct-Horse-1234', role: 'host' },
  })
  expect(registration.status()).toBe(201)
  const session = await registration.json() as { accessToken: string }
  const created = await api.post('/listings', {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: listingPayload(title),
  })
  expect(created.status()).toBe(201)

  const consoleErrors: string[] = []
  page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByText(title, { exact: true }).first()).toBeVisible()
  expect(consoleErrors).toEqual([])
  await api.dispose()
})

test('room count filter is executed by the backend and reflected in mobile results', async ({ page }) => {
  const failedResponses: string[] = []
  page.on('response', (response) => {
    if (response.url().includes('/api/v1/') && response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`)
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&habitaciones=4')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.locator('[data-listing-id]').first()).toBeVisible()
  expect(failedResponses).toEqual([])
})
