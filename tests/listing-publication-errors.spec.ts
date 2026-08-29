import { expect, test, type Page, type Route } from '@playwright/test'

const host = {
  id: '11111111-1111-4111-8111-111111111111',
  name: 'Anfitrión de prueba',
  email: 'publication-ui@example.com',
  role: 'host',
  phone: '+34 600 111 222',
  whatsapp: '+34 600 111 223',
  telegram: '',
  about: '',
  initials: 'AP',
  showPhone: true,
  showWhatsApp: true,
  emailVerified: true,
  blocked: false,
  avatarUrl: null,
}

type PublicationMode = 'email' | 'validation' | 'success'
type PublicationTestState = {
  mode: PublicationMode
  posts: number
  profilePatches: number
  payload?: Record<string, unknown>
  imageFailures?: number
  imageListingIds?: string[]
  mine?: ReturnType<typeof listingResponse>[]
  publicListings?: ReturnType<typeof listingResponse>[]
  publicListingsAfterFirstSearch?: ReturnType<typeof listingResponse>[]
  searchCalls?: number
  catalogVersions?: string[]
  favoriteIds?: string[]
  statusPatches?: string[]
}

function lifecycleListing(status: 'pending' | 'published' | 'hidden' | 'closed' | 'rejected', id = '33333333-3333-4333-8333-333333333333') {
  return { ...listingResponse({
    title: 'Anuncio lifecycle remoto', city: 'Adeje', area: 'Costa Adeje', approximateAddress: 'Costa Adeje · ubicación aproximada',
    rentalMode: 'long', monthlyPrice: 650, nightlyPrice: null, weeklyPrice: null, roomType: 'Habitación individual',
    availableFrom: '2026-09-01', availableUntil: null, minimumStayMonths: 1, minimumNights: null,
    depositAmount: 650, depositText: null, billsIncluded: true, billsText: 'Gastos incluidos',
    bathroom: 'Baño compartido', kitchen: 'Cocina compartida', furnished: true, roomSizeM2: 14,
    bedroomCount: 3, currentResidents: 2, roomCapacity: 1, shower: 'Ducha compartida',
    homeSizeM2: 80, bathroomCount: 2, rentalUnit: 'room', bedType: 'single', bedCount: 1,
    currentRoomResidents: 0, availableSpots: 1, toilet: 'Aseo compartido', householdGender: 'mixed',
    householdHasChildren: false, heatingType: 'none', accessible: false, floor: '2', couplesAllowed: false,
    acceptedTenantTypes: ['man', 'woman'], tenantRequirement: 'any', smokingAllowed: false, petsAllowed: false,
    childrenAllowed: false, empadronamientoAllowed: true, restrictions: [], amenities: ['Wi-Fi'],
    latitude: 28.09, longitude: -16.73, description: 'Lifecycle consumer regression.', homeDescription: 'Shared home.',
    advertiserType: 'Particular', source: null, expiresAt: '2026-12-31T00:00:00Z', imageUrls: [],
  }, id), status }
}

function listingResponse(payload: Record<string, unknown>, id: string) {
  return {
    id,
    ownerUserId: host.id,
    owner: { name: host.name, initials: host.initials, since: '2026-01-01T00:00:00Z', response: 'Consulta disponibilidad', verified: true },
    contactPhone: host.phone,
    contactWhatsapp: host.whatsapp,
    contactEmail: null,
    showPhone: true,
    showWhatsApp: true,
    coverImageUrl: null,
    imageUrls: [],
    ...payload,
    price: payload.monthlyPrice,
    cadence: 'mes',
    status: 'pending',
    advertiserName: null,
    isExternal: false,
    primarySource: null,
    sourceUrl: null,
    sourcePriceText: null,
    priceCurrency: null,
    pricePeriod: null,
    priceIsFrom: null,
    publishedAt: null,
    views: 0,
    closedReason: null,
    createdAt: '2026-08-28T00:00:00Z',
    updatedAt: null,
    promoted: false,
  }
}

async function mockPublicationApi(page: Page, state: PublicationTestState) {
  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => route.fulfill({ status, contentType: 'application/json', headers, body: JSON.stringify(value) })

    if (path === '/auth/refresh') return json({ accessToken: 'publication-test-token', user: host })
    if (path === '/auth/email-verification/status') return json({ verified: true, email: host.email })
    if (path === '/listings/search') {
      state.searchCalls = (state.searchCalls ?? 0) + 1
      const items = state.searchCalls > 1 && state.publicListingsAfterFirstSearch
        ? state.publicListingsAfterFirstSearch
        : state.publicListings ?? []
      return json({ items, total: items.length, limit: 100, offset: 0 })
    }
    if (path === '/listings/catalog-version') return json({ version: state.catalogVersions?.shift() ?? '1', updatedAt: '2026-08-28T00:00:00Z' })
    if (path === '/listings/mine') return json(state.mine ?? [])
    if (/^\/listings\/[^/]+$/.test(path) && request.method() === 'PATCH') {
      const next = (request.postDataJSON() as { status: 'pending' | 'published' | 'hidden' | 'closed' | 'rejected' }).status
      state.statusPatches?.push(next)
      const updated = lifecycleListing(next, path.split('/')[2])
      state.mine = [updated]
      return json(updated)
    }
    if (path === '/users/me' && request.method() === 'PATCH') {
      state.profilePatches += 1
      return json(host)
    }
    if (path === '/listings' && request.method() === 'POST') {
      state.posts += 1
      state.payload = request.postDataJSON() as Record<string, unknown>
      if (state.mode === 'email') return json({ code: 'EMAIL_VERIFICATION_REQUIRED', message: 'Confirm email', fieldErrors: {} }, 409, { 'X-Request-ID': 'email-request' })
      if (state.mode === 'validation') return json({ detail: [{ loc: ['body', 'monthlyPrice'], msg: 'Field required' }] }, 422, { 'X-Request-ID': 'validation-request' })
      const key = request.headers()['idempotency-key']
      return json(listingResponse(state.payload, key), 201)
    }
    if (path === '/uploads' && request.method() === 'POST') return json({ id: '22222222-2222-4222-8222-222222222222', url: '/api/v1/media/22222222-2222-4222-8222-222222222222' }, 201)
    if (/^\/listings\/[^/]+\/images$/.test(path) && request.method() === 'PUT') {
      state.imageListingIds?.push(path.split('/')[2])
      if ((state.imageFailures ?? 0) > 0) {
        state.imageFailures = (state.imageFailures ?? 0) - 1
        return json({ code: 'internal_error', message: 'Internal server error', fieldErrors: {} }, 500)
      }
      return json([{ assetId: '22222222-2222-4222-8222-222222222222', url: '/api/v1/media/22222222-2222-4222-8222-222222222222', sortOrder: 0, isCover: true }])
    }
    if (path === '/favorites') return json(state.favoriteIds ?? [])
    if (['/discarded-listings', '/saved-searches', '/search-history', '/reports'].includes(path)) return json([])
    if (path === '/users/me/restriction') return json(null)
    if (path === '/users/me/moderation-notices') return json([])
    return json({ detail: `Unhandled test route: ${request.method()} ${path}` }, 404)
  })
}

async function openCompletedWizard(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:has-session', '1')
    // The suite also runs against the local mock provider. Keep both auth
    // hints so the helper is deterministic in either runtime mode.
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.reload()
  await page.goto('/#/publicar')
  await expect(page.getByRole('heading', { name: 'Publicar una habitación' })).toBeVisible()
  for (let step = 0; step < 9; step += 1) {
    if (step === 6) {
      await page.getByLabel('Añadir fotos del anuncio').setInputFiles({
        name: 'synthetic-room.png',
        mimeType: 'image/png',
        buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
      })
      await expect(page.locator('.upload-grid > div')).toHaveCount(1)
    }
    await page.getByRole('button', { name: 'Continuar' }).click()
  }
  await expect(page.getByRole('button', { name: 'Publicar anuncio' })).toBeVisible()
}

test('publication preserves email and FastAPI validation errors in Spanish', async ({ page }) => {
  const state = { mode: 'email' as PublicationMode, posts: 0, profilePatches: 0 }
  await mockPublicationApi(page, state)
  await openCompletedWizard(page)

  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Confirma tu email antes de publicar el anuncio.')).toBeVisible()

  state.mode = 'validation'
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Revisa el precio mensual.')).toBeVisible()
  await expect(page.getByText('No se pudo publicar el anuncio en el servidor.')).toHaveCount(0)
  expect(state.posts).toBe(2)
  expect(state.profilePatches).toBe(0)
})

test('double click sends one idempotent publication and then synchronizes images', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0, payload: undefined as Record<string, unknown> | undefined }
  await mockPublicationApi(page, state)
  await openCompletedWizard(page)

  const publish = page.getByRole('button', { name: 'Publicar anuncio' })
  await publish.dblclick()
  await expect(page.getByRole('heading', { name: 'Tu anuncio se ha enviado a revisión' })).toBeVisible()

  expect(state.posts).toBe(1)
  expect(state.profilePatches).toBe(0)
  expect(state.payload).toMatchObject({
    contactName: host.name,
    contactPhone: host.phone,
    contactWhatsapp: host.whatsapp,
    showPhone: true,
    showWhatsApp: true,
  })
  expect(state.payload).not.toHaveProperty('source')
  expect(state.payload).not.toHaveProperty('ownerUserId')
  expect(state.payload).not.toHaveProperty('status')
})

test('publish revalidates earlier steps after the host revisits and changes them', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0 }
  await mockPublicationApi(page, state)
  await openCompletedWizard(page)

  await page.locator('.stepper').getByRole('button', { name: /Habitación/ }).click()
  await page.getByLabel('Superficie total de la vivienda (m²)').fill('5')
  await page.locator('.stepper').getByRole('button', { name: /Vista previa/ }).click()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()

  await expect(page.getByText('La vivienda debe tener una superficie entera, igual o mayor que la habitación.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Describe la habitación' })).toBeVisible()
  expect(state.posts).toBe(0)
})

test('image failure keeps the durable draft and retries images without reposting or editing fields', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0, imageFailures: 1, imageListingIds: [] as string[] }
  await mockPublicationApi(page, state)
  await openCompletedWizard(page)

  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText(/El anuncio se creó, pero/)).toBeVisible()
  await expect(page.getByText(/Los datos del anuncio están bloqueados/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Tu anuncio se ha enviado a revisión' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reintentar fotografías' })).toBeEnabled()
  expect(state.posts).toBe(1)
  expect(state.imageListingIds).toHaveLength(1)
  expect(await page.evaluate(() => localStorage.getItem('112233:listing-draft:v3'))).toBeTruthy()

  await page.locator('.stepper').getByRole('button', { name: /Contacto/ }).click()
  await expect(page.getByRole('heading', { name: 'Revisa antes de publicar' })).toBeVisible()
  await page.getByRole('button', { name: 'Reintentar fotografías' }).click()
  await expect(page.getByRole('heading', { name: 'Tu anuncio se ha enviado a revisión' })).toBeVisible()
  expect(state.posts).toBe(1)
  expect(state.imageListingIds).toHaveLength(2)
  expect(state.imageListingIds[1]).toBe(state.imageListingIds[0])
})

test('publication contact validation matches the backend for hidden values and limits', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0 }
  await mockPublicationApi(page, state)
  await openCompletedWizard(page)

  await page.locator('.stepper').getByRole('button', { name: /Contacto/ }).click()
  await page.locator('#publish-contact-phone').fill('not-a-phone')
  await page.getByRole('checkbox', { name: 'Mostrar teléfono tras confirmar' }).uncheck()
  await page.locator('.stepper').getByRole('button', { name: /Vista previa/ }).click()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Introduce un teléfono válido.')).toBeVisible()
  expect(state.posts).toBe(0)

  await page.locator('.stepper').getByRole('button', { name: /Contacto/ }).click()
  await page.locator('#publish-contact-phone').fill('1'.repeat(65))
  await page.locator('.stepper').getByRole('button', { name: /Vista previa/ }).click()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('El teléfono no puede superar 64 caracteres.')).toBeVisible()
  expect(state.posts).toBe(0)

  await page.locator('.stepper').getByRole('button', { name: /Contacto/ }).click()
  await page.locator('#publish-contact-phone').fill(host.phone)
  await page.getByRole('checkbox', { name: 'Mostrar teléfono tras confirmar' }).check()
  await page.locator('#publish-contact-whatsapp').fill('')
  await page.getByRole('checkbox', { name: 'Permitir WhatsApp tras confirmar' }).uncheck()
  await page.locator('.stepper').getByRole('button', { name: /Vista previa/ }).click()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByRole('heading', { name: 'Tu anuncio se ha enviado a revisión' })).toBeVisible()
  expect(state.posts).toBe(1)
})

test('catalog hydration retries when a lifecycle mutation races the public snapshot', async ({ page }) => {
  const published = lifecycleListing('published')
  const state: PublicationTestState = {
    mode: 'success', posts: 0, profilePatches: 0,
    publicListings: [], publicListingsAfterFirstSearch: [published], catalogVersions: ['1', '2', '2'],
    favoriteIds: [published.id],
  }
  await mockPublicationApi(page, state)
  await page.addInitScript(() => localStorage.setItem('112233:has-session', '1'))
  await page.goto('/#/favoritos')

  await expect(page.locator('.property-card').filter({ hasText: published.title })).toHaveCount(1)
  expect(state.searchCalls).toBeGreaterThanOrEqual(2)
})

test('pending owner listings survive reload without leaking into public search or map state', async ({ page }) => {
  const pending = lifecycleListing('pending')
  const state: PublicationTestState = {
    mode: 'success', posts: 0, profilePatches: 0, mine: [pending], publicListings: [], statusPatches: [],
  }
  await mockPublicationApi(page, state)
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:has-session', '1'))
  await page.reload()

  await page.goto('/#/mis-anuncios')
  await expect(page.getByText('Anuncio lifecycle remoto', { exact: true })).toBeVisible()
  await expect(page.locator('.manage-card')).toContainText('Pendiente')

  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await expect(page.getByText('Anuncio lifecycle remoto', { exact: true })).toHaveCount(0)
})

test('owner show intent returns a hidden listing to moderation and refreshes every listing consumer', async ({ page }) => {
  const hidden = lifecycleListing('hidden')
  const state: PublicationTestState = {
    mode: 'success', posts: 0, profilePatches: 0, mine: [hidden], publicListings: [], statusPatches: [],
  }
  await mockPublicationApi(page, state)
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:has-session', '1'))
  await page.reload()
  await page.goto('/#/mis-anuncios')

  const card = page.locator('.manage-card')
  await card.getByRole('button', { name: /Más acciones/ }).click()
  await page.getByRole('menuitem', { name: 'Enviar a revisión' }).click()
  await expect(card).toContainText('Pendiente')
  expect(state.statusPatches).toEqual(['pending'])
})
