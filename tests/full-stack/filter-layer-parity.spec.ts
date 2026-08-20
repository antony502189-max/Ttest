import { expect, request as playwrightRequest, test, type APIRequestContext, type Page } from '@playwright/test'

const API = 'http://127.0.0.1:8000'
const API_PREFIX = '/api/v1'
let clientCounter = 180

function nextIp() {
  return `192.0.2.${clientCounter++}`
}

async function verifiedHost(unique: string) {
  const api = await playwrightRequest.newContext({
    baseURL: API,
    extraHTTPHeaders: { Origin: 'http://127.0.0.1:4174', 'X-Real-IP': nextIp() },
  })
  const registration = await api.post(`${API_PREFIX}/auth/register`, {
    data: { name: 'Filter Audit Host', email: `filter-${unique}@example.com`, password: 'Correct-Horse-1234', role: 'host' },
  })
  expect(registration.status()).toBe(201)
  const session = await registration.json() as { accessToken: string }
  const requested = await api.post(`${API_PREFIX}/auth/email-verification/request`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
  })
  expect(requested.status()).toBe(202)
  const { verificationCode } = await requested.json() as { verificationCode: string }
  const confirmed = await api.post(`${API_PREFIX}/auth/email-verification/confirm`, {
    headers: { Authorization: `Bearer ${session.accessToken}` },
    data: { code: verificationCode },
  })
  expect(confirmed.status()).toBe(204)
  await api.dispose()
  return session.accessToken
}

function baseListing(title: string, city: string, area: string) {
  return {
    title,
    city,
    area,
    street: 'Private audit street',
    postcode: '38001',
    approximateAddress: `${area} · ubicación aproximada`,
    rentalMode: 'long',
    monthlyPrice: 725,
    nightlyPrice: null,
    weeklyPrice: null,
    roomType: 'Habitación individual',
    availableFrom: '2026-01-01',
    availableUntil: '2030-12-31',
    minimumStayMonths: 1,
    minimumNights: null,
    depositAmount: 0,
    billsIncluded: true,
    billsText: 'Gastos incluidos',
    bathroom: 'Baño privado',
    kitchen: 'Cocina privada',
    furnished: true,
    roomSizeM2: 18,
    bedroomCount: 4,
    currentResidents: 5,
    roomCapacity: 2,
    shower: 'Ducha privada',
    homeSizeM2: 90,
    bathroomCount: 2,
    rentalUnit: 'room',
    bedType: 'double',
    bedCount: 1,
    currentRoomResidents: 1,
    toilet: 'Aseo privado',
    householdGender: 'mixed',
    householdHasChildren: false,
    heatingType: 'individual',
    accessible: true,
    floor: 'top',
    couplesAllowed: true,
    acceptedTenantTypes: ['man', 'woman'],
    tenantRequirement: 'single-man',
    smokingAllowed: true,
    petsAllowed: true,
    childrenAllowed: false,
    empadronamientoAllowed: true,
    restrictions: ['No fumar', 'Gastos incluidos'],
    amenities: ['Wi-Fi', 'Aire acondicionado', 'Jardín'],
    latitude: 28.4636,
    longitude: -16.2518,
    exactLatitude: 28.464,
    exactLongitude: -16.2514,
    description: 'Filter layer audit listing.',
    homeDescription: 'Structured room facts for filter parity.',
    advertiserType: 'Profesional',
    source: 'filter-layer-audit',
    expiresAt: '2099-12-31T00:00:00Z',
  }
}

async function createListing(api: APIRequestContext, token: string, payload: Record<string, unknown>) {
  const response = await api.post(`${API_PREFIX}/listings`, {
    headers: { Authorization: `Bearer ${token}` },
    data: payload,
  })
  expect(response.status()).toBe(201)
  return (await response.json() as { id: string }).id
}

async function searchIds(api: APIRequestContext, payload: Record<string, unknown>) {
  const response = await api.post(`${API_PREFIX}/listings/search`, { data: { ...payload, limit: 100, offset: 0 } })
  expect(response.status(), JSON.stringify(payload)).toBe(200)
  const body = await response.json() as { items: Array<{ id: string }> }
  return body.items.map((item) => item.id)
}

async function expectFilter(
  api: APIRequestContext,
  listingId: string,
  isolation: Record<string, unknown>,
  match: Record<string, unknown>,
  miss: Record<string, unknown>,
  name: string,
) {
  expect(await searchIds(api, { ...isolation, ...match }), `${name}: matching query`).toContain(listingId)
  expect(await searchIds(api, { ...isolation, ...miss }), `${name}: rejecting query`).not.toContain(listingId)
}

function encodedSearch(mode: 'long' | 'holiday', params: Record<string, string>) {
  const search = new URLSearchParams({ q: 'Tenerife', alquiler: mode, ...params })
  return `/#/buscar?${search.toString()}`
}

async function expectSerialized(
  page: Page,
  bodies: Record<string, unknown>[],
  mode: 'long' | 'holiday',
  params: Record<string, string>,
  key: string,
  expected: unknown,
) {
  bodies.splice(0)
  await page.goto(encodedSearch(mode, params))
  await expect.poll(
    () => bodies.some((body) => JSON.stringify(body[key]) === JSON.stringify(expected)),
    { message: `${key} was not serialized as ${JSON.stringify(expected)}` },
  ).toBe(true)
}

test('FILTER-LAYER desktop URL state serializes every server-backed filter into the FastAPI request', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'mobile-chromium', 'Mobile results consume the fully paginated catalog and use the shared client filter engine; URL-to-FastAPI serialization is a desktop-path contract.')
  const bodies: Record<string, unknown>[] = []
  await page.route('**/api/v1/listings/search', async (route) => {
    bodies.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({ json: { items: [], total: 0, limit: 100, offset: 0 } })
  })

  const cases: Array<{ mode?: 'long' | 'holiday'; params: Record<string, string>; key: string; expected: unknown }> = [
    { params: { precioMin: '450' }, key: 'minPrice', expected: 450 },
    { params: { precioMax: '800' }, key: 'maxPrice', expected: 800 },
    { params: { habitacion: 'Habitación individual' }, key: 'roomType', expected: 'Habitación individual' },
    { params: { fecha: '2028-01-01' }, key: 'availableFrom', expected: '2028-01-01' },
    { params: { hasta: '2030-01-01' }, key: 'availableUntil', expected: '2030-01-01' },
    { params: { estancia: '2' }, key: 'maxMinimumStayMonths', expected: 2 },
    { params: { condiciones: 'No fumar|Gastos incluidos' }, key: 'restrictions', expected: ['No fumar', 'Gastos incluidos'] },
    { params: { requisito: 'single-man' }, key: 'tenantRequirement', expected: 'single-man' },
    { params: { bano: 'Baño privado' }, key: 'bathroom', expected: 'Baño privado' },
    { params: { cocina: 'Cocina privada' }, key: 'kitchen', expected: 'Cocina privada' },
    { params: { amueblada: '1' }, key: 'furnished', expected: true },
    { params: { gastos: '1' }, key: 'billsIncluded', expected: true },
    { params: { fianza: 'Sin fianza' }, key: 'deposit', expected: 'Sin fianza' },
    { params: { tamanoMin: '12' }, key: 'minRoomSizeM2', expected: 12 },
    { params: { tamanoMax: '30' }, key: 'maxRoomSizeM2', expected: 30 },
    { params: { viviendaMin: '70' }, key: 'minHomeSizeM2', expected: 70 },
    { params: { viviendaMax: '120' }, key: 'maxHomeSizeM2', expected: 120 },
    { params: { banosMin: '2' }, key: 'minBathroomCount', expected: 2 },
    { params: { unidad: 'room' }, key: 'rentalUnit', expected: 'room' },
    { params: { cama: 'double' }, key: 'bedType', expected: 'double' },
    { params: { camasMin: '1' }, key: 'minBedCount', expected: 1 },
    { params: { ducha: 'Ducha privada' }, key: 'shower', expected: 'Ducha privada' },
    { params: { aseo: 'Aseo privado' }, key: 'toilet', expected: 'Aseo privado' },
    { params: { residentes: '5+' }, key: 'minCurrentResidents', expected: 5 },
    { params: { residentesHabitacion: '1' }, key: 'currentRoomResidents', expected: 1 },
    { params: { capacidad: '2' }, key: 'roomCapacity', expected: 2 },
    { params: { plazasMin: '1' }, key: 'minAvailableSpots', expected: 1 },
    { mode: 'holiday', params: { nochesMin: '3' }, key: 'maxMinimumNights', expected: 3 },
    { params: { fumar: 'Sí' }, key: 'smokingAllowed', expected: true },
    { params: { mascotas: 'No' }, key: 'petsAllowed', expected: false },
    { params: { ninos: 'Sí' }, key: 'childrenAllowed', expected: true },
    { params: { parejasOk: 'Sí' }, key: 'couplesAllowed', expected: true },
    { params: { convivenciaGenero: 'mixed' }, key: 'householdGender', expected: 'mixed' },
    { params: { convivenciaNinos: 'No' }, key: 'householdHasChildren', expected: false },
    { params: { calefaccion: 'individual' }, key: 'heatingType', expected: 'individual' },
    { params: { adaptada: 'Sí' }, key: 'accessible', expected: true },
    { params: { planta: 'top' }, key: 'floor', expected: 'top' },
    { params: { acepta: 'man|woman' }, key: 'acceptedTenantTypes', expected: ['man', 'woman'] },
    { params: { padron: 'Sí' }, key: 'empadronamientoAllowed', expected: true },
    { params: { publicado: '7d' }, key: 'publishedWithinDays', expected: 7 },
    { params: { anunciante: 'Profesional' }, key: 'advertiserType', expected: 'Profesional' },
    { params: { servicios: 'Aire acondicionado|Jardín' }, key: 'amenities', expected: ['Aire acondicionado', 'Jardín'] },
    { params: { orden: 'Precio más bajo' }, key: 'sort', expected: 'price_asc' },
    { params: { cerca: '1', lat: '28.4636', lng: '-16.2518', radio: '5' }, key: 'radiusKm', expected: 5 },
  ]

  for (const item of cases) {
    await expectSerialized(page, bodies, item.mode ?? 'long', item.params, item.key, item.expected)
  }

  bodies.splice(0)
  await page.goto(encodedSearch('long', { requisito: 'any' }))
  await expect.poll(() => bodies.length).toBeGreaterThan(0)
  expect(bodies[0]).not.toHaveProperty('tenantRequirement')

  bodies.splice(0)
  await page.goto(encodedSearch('long', { poligono: '28.46000,-16.26000;28.47000,-16.26000;28.47000,-16.24500' }))
  await expect.poll(() => bodies.some((body) => Array.isArray(body.polygon) && body.polygon.length >= 3)).toBe(true)
})

test('FILTER-LAYER FastAPI + PostgreSQL predicates include matches and reject non-matches for every server filter', async ({ page }) => {
  test.setTimeout(120_000)
  const unique = `${Date.now()}-${test.info().project.name}`
  const city = `Filter Audit ${unique}`
  const area = `Audit Area ${unique}`
  const token = await verifiedHost(unique)
  const api = await playwrightRequest.newContext({
    baseURL: API,
    extraHTTPHeaders: { Origin: 'http://127.0.0.1:4174', Authorization: `Bearer ${token}`, 'X-Real-IP': nextIp() },
  })

  const primaryId = await createListing(api, token, baseListing(`Primary ${unique}`, city, area))
  const secondaryId = await createListing(api, token, { ...baseListing(`Secondary ${unique}`, city, area), monthlyPrice: 925, floor: '1', amenities: ['Wi-Fi'] })
  const holidayId = await createListing(api, token, {
    ...baseListing(`Holiday ${unique}`, city, area),
    rentalMode: 'holiday', monthlyPrice: null, nightlyPrice: 80, minimumStayMonths: 0, minimumNights: 3,
  })

  const isolation = { query: city, rentalMode: 'long' }
  const checks: Array<{ name: string; match: Record<string, unknown>; miss: Record<string, unknown> }> = [
    { name: 'min price', match: { minPrice: 700 }, miss: { minPrice: 726 } },
    { name: 'max price', match: { maxPrice: 800 }, miss: { maxPrice: 724 } },
    { name: 'room type', match: { roomType: 'Habitación individual' }, miss: { roomType: 'Estudio' } },
    { name: 'room types', match: { roomTypes: ['Habitación individual'] }, miss: { roomTypes: ['Estudio'] } },
    { name: 'bedroom counts', match: { bedroomCounts: [4] }, miss: { bedroomCounts: [3] } },
    { name: 'available date', match: { availableFrom: '2028-01-01' }, miss: { availableFrom: '2031-01-01' } },
    { name: 'move-out horizon', match: { availableUntil: '2030-01-01' }, miss: { availableUntil: '2031-01-01' } },
    { name: 'minimum stay', match: { maxMinimumStayMonths: 1 }, miss: { maxMinimumStayMonths: 0 } },
    { name: 'restrictions', match: { restrictions: ['No fumar'] }, miss: { restrictions: ['Mascotas permitidas'] } },
    { name: 'tenant requirement', match: { tenantRequirement: 'single-man' }, miss: { tenantRequirement: 'couple' } },
    { name: 'bathroom', match: { bathroom: 'Baño privado' }, miss: { bathroom: 'Baño compartido' } },
    { name: 'kitchen', match: { kitchen: 'Cocina privada' }, miss: { kitchen: 'Cocina compartida' } },
    { name: 'furnished', match: { furnished: true }, miss: { furnished: false } },
    { name: 'bills included', match: { billsIncluded: true }, miss: { billsIncluded: false } },
    { name: 'deposit', match: { deposit: 'Sin fianza' }, miss: { deposit: 'Más de 1 mes' } },
    { name: 'minimum room size', match: { minRoomSizeM2: 18 }, miss: { minRoomSizeM2: 19 } },
    { name: 'maximum room size', match: { maxRoomSizeM2: 18 }, miss: { maxRoomSizeM2: 17 } },
    { name: 'minimum home size', match: { minHomeSizeM2: 90 }, miss: { minHomeSizeM2: 91 } },
    { name: 'maximum home size', match: { maxHomeSizeM2: 90 }, miss: { maxHomeSizeM2: 89 } },
    { name: 'bathroom count', match: { minBathroomCount: 2 }, miss: { minBathroomCount: 3 } },
    { name: 'rental unit', match: { rentalUnit: 'room' }, miss: { rentalUnit: 'bed' } },
    { name: 'bed type', match: { bedType: 'double' }, miss: { bedType: 'single' } },
    { name: 'bed count', match: { minBedCount: 1 }, miss: { minBedCount: 2 } },
    { name: 'shower', match: { shower: 'Ducha privada' }, miss: { shower: 'Ducha compartida' } },
    { name: 'toilet', match: { toilet: 'Aseo privado' }, miss: { toilet: 'Aseo compartido' } },
    { name: 'current residents', match: { currentResidents: 5 }, miss: { currentResidents: 4 } },
    { name: 'minimum current residents', match: { minCurrentResidents: 5 }, miss: { minCurrentResidents: 6 } },
    { name: 'room residents', match: { currentRoomResidents: 1 }, miss: { currentRoomResidents: 0 } },
    { name: 'room capacity', match: { roomCapacity: 2 }, miss: { roomCapacity: 1 } },
    { name: 'available spots', match: { minAvailableSpots: 1 }, miss: { minAvailableSpots: 2 } },
    { name: 'smoking', match: { smokingAllowed: true }, miss: { smokingAllowed: false } },
    { name: 'pets', match: { petsAllowed: true }, miss: { petsAllowed: false } },
    { name: 'children', match: { childrenAllowed: false }, miss: { childrenAllowed: true } },
    { name: 'couples', match: { couplesAllowed: true }, miss: { couplesAllowed: false } },
    { name: 'household gender', match: { householdGender: 'mixed' }, miss: { householdGender: 'women' } },
    { name: 'household children', match: { householdHasChildren: false }, miss: { householdHasChildren: true } },
    { name: 'heating', match: { heatingType: 'individual' }, miss: { heatingType: 'central' } },
    { name: 'accessible', match: { accessible: true }, miss: { accessible: false } },
    { name: 'floor', match: { floor: 'top' }, miss: { floor: '2' } },
    { name: 'accepted tenant types', match: { acceptedTenantTypes: ['woman'] }, miss: { acceptedTenantTypes: ['family'] } },
    { name: 'registration', match: { empadronamientoAllowed: true }, miss: { empadronamientoAllowed: false } },
    { name: 'advertiser', match: { advertiserType: 'Profesional' }, miss: { advertiserType: 'Particular' } },
    { name: 'amenities', match: { amenities: ['Aire acondicionado', 'Jardín'] }, miss: { amenities: ['Piscina'] } },
    { name: 'bounding box', match: { minLatitude: 28.45, maxLatitude: 28.48, minLongitude: -16.27, maxLongitude: -16.24 }, miss: { minLatitude: 28.0, maxLatitude: 28.1, minLongitude: -16.8, maxLongitude: -16.7 } },
    { name: 'radius', match: { center: { latitude: 28.4636, longitude: -16.2518 }, radiusKm: 1 }, miss: { center: { latitude: 28.1, longitude: -16.7 }, radiusKm: 1 } },
    { name: 'polygon', match: { polygon: [{ latitude: 28.45, longitude: -16.27 }, { latitude: 28.48, longitude: -16.27 }, { latitude: 28.48, longitude: -16.24 }, { latitude: 28.45, longitude: -16.24 }] }, miss: { polygon: [{ latitude: 28.0, longitude: -16.8 }, { latitude: 28.1, longitude: -16.8 }, { latitude: 28.1, longitude: -16.7 }] } },
  ]

  for (const item of checks) await expectFilter(api, primaryId, isolation, item.match, item.miss, item.name)

  expect(await searchIds(api, { query: city, rentalMode: 'holiday', maxMinimumNights: 3 })).toContain(holidayId)
  expect(await searchIds(api, { query: city, rentalMode: 'holiday', maxMinimumNights: 2 })).not.toContain(holidayId)
  expect(await searchIds(api, { query: city, rentalMode: 'long', publishedWithinDays: 1 })).toContain(primaryId)

  const ascending = await searchIds(api, { query: city, rentalMode: 'long', sort: 'price_asc' })
  expect(ascending.indexOf(primaryId)).toBeLessThan(ascending.indexOf(secondaryId))
  const descending = await searchIds(api, { query: city, rentalMode: 'long', sort: 'price_desc' })
  expect(descending.indexOf(secondaryId)).toBeLessThan(descending.indexOf(primaryId))

  const mine = await api.get(`${API_PREFIX}/listings/mine`)
  expect(mine.status()).toBe(200)
  const owned = (await mine.json() as Array<Record<string, unknown>>).find((item) => item.id === primaryId)
  expect(owned).toMatchObject({
    floor: 'top', toilet: 'Aseo privado', bedType: 'double', bathroomCount: 2,
    homeSizeM2: 90, currentRoomResidents: 1, accessible: true,
    street: 'Private audit street', postcode: '38001', exactLatitude: 28.464, exactLongitude: -16.2514,
  })

  const publicResult = await api.post(`${API_PREFIX}/listings/search`, { data: { query: city, rentalMode: 'long', floor: 'top', limit: 100, offset: 0 } })
  const publicListing = (await publicResult.json() as { items: Array<Record<string, unknown>> }).items.find((item) => item.id === primaryId)
  expect(publicListing).toBeTruthy()
  expect(publicListing).not.toHaveProperty('street')
  expect(publicListing).not.toHaveProperty('postcode')
  expect(publicListing).not.toHaveProperty('exactLatitude')
  expect(publicListing).not.toHaveProperty('exactLongitude')

  await api.dispose()
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
})