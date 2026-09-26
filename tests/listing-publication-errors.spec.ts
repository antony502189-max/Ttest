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
const secondHost = { ...host, id: '44444444-4444-4444-8444-444444444444', name: 'Segunda anfitriona', email: 'second-publication-ui@example.com' }

const syntheticRoomPng = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64')
const requiredPhotoFiles = () => Array.from({ length: 5 }, (_, index) => ({
  name: `synthetic-room-${index + 1}.png`,
  mimeType: 'image/png',
  buffer: syntheticRoomPng,
}))
const mockUploadAssetId = (call: number) => `22222222-2222-4222-8222-${String(222222222221 + call).padStart(12, '0')}`
const requiredServerImageUrls = () => Array.from({ length: 5 }, (_, index) => `/api/v1/media/${mockUploadAssetId(index + 1)}`)

type PublicationMode = 'email' | 'validation' | 'duplicate' | 'success'
type PublicationTestState = {
  mode: PublicationMode
  posts: number
  profilePatches: number
  payload?: Record<string, unknown>
  imageFailures?: number
  imageListingIds?: string[]
  uploadFailures?: number
  uploadCalls?: number
  deletedUploadIds?: string[]
  mine?: ReturnType<typeof listingResponse>[]
  publicListings?: ReturnType<typeof listingResponse>[]
  publicListingsAfterFirstSearch?: ReturnType<typeof listingResponse>[]
  searchCalls?: number
  catalogVersions?: string[]
  favoriteIds?: string[]
  statusPatches?: string[]
  listingPatches?: Record<string, unknown>[]
  authUser?: typeof host
  loginUser?: typeof host
  mineWait?: Promise<void>
  mineCalls?: number
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

    if (path === '/auth/refresh') return json({ accessToken: 'publication-test-token', user: state.authUser ?? host })
    if (path === '/auth/login') return json({ accessToken: 'publication-test-token', user: state.loginUser ?? host })
    if (path === '/auth/logout') return json({})
    if (path === '/auth/email-verification/status') return json({ verified: true, email: host.email })
    if (path === '/listings/search') {
      state.searchCalls = (state.searchCalls ?? 0) + 1
      const items = state.searchCalls > 1 && state.publicListingsAfterFirstSearch
        ? state.publicListingsAfterFirstSearch
        : state.publicListings ?? []
      return json({ items, total: items.length, limit: 100, offset: 0 })
    }
    if (path === '/listings/catalog-version') return json({ version: state.catalogVersions?.shift() ?? '1', updatedAt: '2026-08-28T00:00:00Z' })
    if (path === '/listings/mine') {
      state.mineCalls = (state.mineCalls ?? 0) + 1
      const items = state.mine ?? []
      const wait = state.mineWait
      if (wait) await wait
      return json(items)
    }
    if (/^\/listings\/[^/]+$/.test(path) && request.method() === 'PATCH') {
      const patch = request.postDataJSON() as Record<string, unknown>
      state.listingPatches?.push(patch)
      const listingId = path.split('/')[2]
      const current = state.mine?.find((item) => item.id === listingId)
      if (current) {
        const updated = { ...current, ...patch, id: listingId }
        const previousStreet = String(current.street ?? '').trim().toLocaleLowerCase()
        const previousPostcode = String(current.postcode ?? '').trim()
        state.mine = state.mine?.map((item) => {
          if (item.id === listingId) return updated
          const sameAddressGroup = patch.syncAddressGroup === true
            && item.ownerUserId === current.ownerUserId
            && String(item.street ?? '').trim().toLocaleLowerCase() === previousStreet
            && String(item.postcode ?? '').trim() === previousPostcode
          if (!sameAddressGroup) return item
          return {
            ...item,
            city: patch.city,
            area: patch.area,
            street: patch.street,
            postcode: patch.postcode,
            approximateAddress: patch.approximateAddress,
            latitude: patch.latitude,
            longitude: patch.longitude,
            exactLatitude: patch.exactLatitude,
            exactLongitude: patch.exactLongitude,
          }
        })
        if (typeof patch.status === 'string') state.statusPatches?.push(patch.status)
        return json(updated)
      }
      const next = patch.status as 'pending' | 'published' | 'hidden' | 'closed' | 'rejected'
      state.statusPatches?.push(next)
      const updated = lifecycleListing(next, listingId)
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
      if (state.mode === 'duplicate') return json({ code: 'DUPLICATE_LISTING_IMAGES', message: 'Duplicate gallery', fieldErrors: { assetIds: 'duplicate' } }, 409, { 'X-Request-ID': 'duplicate-request' })
      const key = request.headers()['idempotency-key']
      return json(listingResponse(state.payload, key), 201)
    }
    if (/^\/uploads\/[^/]+$/.test(path) && request.method() === 'DELETE') {
      state.deletedUploadIds?.push(path.split('/')[2])
      return route.fulfill({ status: 204, body: '' })
    }
    if (path === '/uploads' && request.method() === 'POST') {
      state.uploadCalls = (state.uploadCalls ?? 0) + 1
      const assetId = mockUploadAssetId(state.uploadCalls)
      if ((state.uploadFailures ?? 0) > 0) {
        state.uploadFailures = (state.uploadFailures ?? 0) - 1
        return json({ code: 'internal_error', message: 'Internal server error', fieldErrors: {} }, 500)
      }
      return json({ id: assetId, url: `/api/v1/media/${assetId}` }, 201)
    }
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

async function openCompletedPublicationForm(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:has-session', '1')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.reload()
  await page.goto('/#/publicar')
  await expect(page.getByRole('heading', { name: 'Publicar habitación' })).toBeVisible()
  await expect(page.locator('.stepper')).toHaveCount(0)

  await page.locator('#publish-city').selectOption('Adeje')
  await page.locator('#publish-area').fill('Costa Adeje')
  await page.locator('#publish-postcode').fill('38660')
  await page.getByLabel('Añadir fotos del anuncio').setInputFiles(requiredPhotoFiles())
  await expect(page.locator('.upload-photo-card')).toHaveCount(5)
  await expect(page.getByRole('button', { name: 'Publicar anuncio' })).toBeVisible()
}

test('publication preserves email and FastAPI validation errors in Spanish', async ({ page }) => {
  const state = { mode: 'email' as PublicationMode, posts: 0, profilePatches: 0 }
  await mockPublicationApi(page, state)
  await openCompletedPublicationForm(page)

  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Confirma tu email antes de publicar el anuncio.')).toBeVisible()

  state.mode = 'validation'
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Revisa el precio mensual.')).toBeVisible()
  await expect(page.getByText('No se pudo publicar el anuncio en el servidor.')).toHaveCount(0)
  expect(state.posts).toBe(2)
  expect(state.profilePatches).toBe(0)
})

test('duplicate photo gallery keeps the exact draft, removes temporary uploads and shows localized replace-photo feedback', async ({ page }) => {
  const state = {
    mode: 'duplicate' as PublicationMode,
    posts: 0,
    profilePatches: 0,
    uploadCalls: 0,
    deletedUploadIds: [] as string[],
  }
  await mockPublicationApi(page, state)
  await openCompletedPublicationForm(page)
  await page.evaluate(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    document.documentElement.lang = 'ru'
  })
  await expect.poll(() => page.evaluate(() => localStorage.getItem('112233:listing-draft:v3'))).not.toBeNull()
  const draftBefore = await page.evaluate(() => localStorage.getItem('112233:listing-draft:v3'))

  const publish = page.getByRole('button', { name: 'Publicar anuncio' })
  const startedAt = Date.now()
  await publish.click()
  await expect(page.getByRole('button', { name: 'Publicando…' }).first()).toBeDisabled()
  await expect(page.getByText('Такое объявление уже существует. Замените фотографии.')).toBeVisible()
  expect(Date.now() - startedAt).toBeGreaterThanOrEqual(900)

  expect(state.uploadCalls).toBe(5)
  expect(state.posts).toBe(1)
  expect(state.deletedUploadIds).toEqual(Array.from({ length: 5 }, (_, index) => mockUploadAssetId(index + 1)))
  await expect(page).toHaveURL(/#\/publicar$/)
  const draftAfter = await page.evaluate(() => localStorage.getItem('112233:listing-draft:v3'))
  expect(draftAfter).toBe(draftBefore)
  expect(draftAfter).toBeTruthy()

  const originalPhoto = await page.locator('.upload-photo-card').first().getAttribute('data-photo-reference')
  await page.getByRole('button', { name: 'Eliminar foto 1' }).click()
  await expect(page.locator('.upload-photo-card.is-dragging')).toHaveCount(0)
  await expect(page.locator('.upload-photo-card')).toHaveCount(4)
  await page.getByLabel('Añadir fotos del anuncio').setInputFiles({
    name: 'replacement-room.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAD0lEQVR4nGP4z8DAwPAfAAcAAf9+CLHQAAAAAElFTkSuQmCC', 'base64'),
  })
  await expect(page.locator('.upload-photo-card')).toHaveCount(5)
  await expect(page.locator(`.upload-photo-card[data-photo-reference="${originalPhoto}"]`)).toHaveCount(0)
  state.mode = 'success'
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  expect(state.posts).toBe(2)
  expect(state.uploadCalls).toBe(10)
})

test('double click sends one idempotent publication and then synchronizes images', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0, payload: undefined as Record<string, unknown> | undefined }
  await mockPublicationApi(page, state)
  await openCompletedPublicationForm(page)

  const publish = page.getByRole('button', { name: 'Publicar anuncio' })
  await publish.dblclick()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)

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
  await openCompletedPublicationForm(page)

  await page.locator('#publish-home-size').fill('5')
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()

  await expect(page.getByText(/igual o mayor que la habitación/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Habitación y vivienda' })).toBeVisible()
  expect(state.posts).toBe(0)
})

test('image upload failure keeps the durable draft and retries before creating the listing', async ({ page }) => {
  const state = {
    mode: 'success' as PublicationMode,
    posts: 0,
    profilePatches: 0,
    uploadFailures: 1,
    uploadCalls: 0,
  }
  await mockPublicationApi(page, state)
  await openCompletedPublicationForm(page)

  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page).toHaveURL(/#\/publicar$/)
  await expect(page.getByRole('button', { name: 'Publicar anuncio' })).toBeEnabled()
  expect(state.uploadCalls).toBeGreaterThanOrEqual(1)
  expect(state.posts).toBe(0)
  expect(await page.evaluate(() => localStorage.getItem('112233:listing-draft:v3'))).toBeTruthy()
  const uploadsAfterFailure = state.uploadCalls

  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  expect(state.uploadCalls).toBeGreaterThan(uploadsAfterFailure)
  expect(state.posts).toBe(1)
  expect(state.payload?.assetIds).toHaveLength(5)
  expect(new Set(state.payload?.assetIds as string[]).size).toBe(5)
})

test('customer video: edit PATCH ignores stale global create draft and persists the current private address', async ({ page }) => {
  const listingId = '33333333-3333-4333-8333-333333333333'
  const imageId = '22222222-2222-4222-8222-222222222222'
  const state: PublicationTestState = {
    mode: 'success',
    posts: 0,
    profilePatches: 0,
    listingPatches: [],
    mine: [{
      ...lifecycleListing('published', listingId),
      street: 'Calle Poetas Españoles 3',
      postcode: '38678',
      exactLatitude: 28.0701,
      exactLongitude: -16.7318,
      latitude: 28.0708,
      longitude: -16.7322,
      imageUrls: requiredServerImageUrls(),
      coverImageUrl: requiredServerImageUrls()[0],
      description: 'Habitación de prueba con una descripción suficientemente larga para validar el formulario.',
    }],
  }
  await mockPublicationApi(page, state)
  await page.goto('/#/')
  await page.evaluate(({ hostId }) => {
    localStorage.clear()
    localStorage.setItem('112233:has-session', '1')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:listing-draft:v3', JSON.stringify({
      version: 3,
      ownerUserId: hostId,
      data: {
        street: 'Calle Poetas Españoles 3',
        postcode: '38678',
        contactName: 'Anfitrión de prueba',
        contactPhone: '+34 600 111 222',
        contactWhatsapp: '+34 600 111 223',
      },
    }))
  }, { hostId: host.id })
  await page.reload()
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('.manage-card')).toHaveCount(1)
  await page.getByRole('link', { name: /editar/i }).click()
  await expect(page.locator('#publish-street')).toHaveValue('Calle Poetas Españoles 3')

  await page.locator('#publish-street').fill('Avenida V Centenario 1')
  await page.locator('#publish-postcode').fill('38660')
  await page.evaluate(() => {
    const detail = {
      formattedAddress: 'Avenida V Centenario 1, 38660 Playa de las Américas, Santa Cruz de Tenerife, Spain',
      coordinates: { lat: 28.0674, lng: -16.7268 },
      addressComponents: [
        { long_name: 'Avenida V Centenario', types: ['route'] },
        { long_name: '1', types: ['street_number'] },
        { long_name: '38660', types: ['postal_code'] },
        { long_name: 'Playa de las Américas', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
    }
    window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail }))
    window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates: detail.coordinates } }))
  })
  await expect(page.locator('#publish-street')).toHaveValue('Avenida V Centenario 1')
  await expect(page.locator('#publish-postcode')).toHaveValue('38660')

  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)

  const patch = state.listingPatches?.at(-1)
  expect(patch).toMatchObject({
    street: 'Avenida V Centenario 1',
    postcode: '38660',
    exactLatitude: 28.0674,
    exactLongitude: -16.7268,
  })
  expect(patch).not.toMatchObject({ street: 'Calle Poetas Españoles 3', postcode: '38678' })

  await page.goto(`/#/mis-anuncios/${listingId}/editar`)
  await expect(page.locator('#publish-street')).toHaveValue('Avenida V Centenario 1')
  await expect(page.locator('#publish-postcode')).toHaveValue('38660')
  await expect(page.locator('.listing-edit-coordinates')).toContainText('28.0674, -16.7268')
})

test('customer follow-up: changing one room address synchronizes sibling rooms from the same old dwelling', async ({ page }) => {
  const firstId = '33333333-3333-4333-8333-333333333333'
  const siblingId = '55555555-5555-4555-8555-555555555555'
  const independentId = '66666666-6666-4666-8666-666666666666'
  const imageId = '22222222-2222-4222-8222-222222222222'
  const base = {
    ...lifecycleListing('published', firstId),
    street: 'Calle Poetas Españoles 3',
    postcode: '38678',
    exactLatitude: 28.0701,
    exactLongitude: -16.7318,
    latitude: 28.0708,
    longitude: -16.7322,
    imageUrls: requiredServerImageUrls(),
    coverImageUrl: requiredServerImageUrls()[0],
    description: 'Habitación de prueba con una descripción suficientemente larga para validar el formulario.',
  }
  const state: PublicationTestState = {
    mode: 'success',
    posts: 0,
    profilePatches: 0,
    listingPatches: [],
    mine: [
      base,
      { ...base, id: siblingId, title: 'Segunda habitación del mismo domicilio', area: 'Adeje', exactLatitude: 28.1227, exactLongitude: -16.7244 },
      { ...base, id: independentId, title: 'Habitación de otra vivienda', street: 'Calle Poetas Españoles 9' },
    ],
  }
  await mockPublicationApi(page, state)
  await page.goto('/#/')
  await page.evaluate(({ siblingId, hostId }) => {
    localStorage.clear()
    localStorage.setItem('112233:has-session', '1')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem(`112233:listing-edit-draft:v1:${siblingId}`, JSON.stringify({
      version: 3,
      ownerUserId: hostId,
      listingId: siblingId,
      data: { street: 'Calle Poetas Españoles 3', postcode: '38678', area: 'Adeje' },
    }))
  }, { siblingId, hostId: host.id })
  await page.reload()
  await page.goto(`/#/mis-anuncios/${firstId}/editar`)
  await expect(page.locator('#publish-street')).toHaveValue('Calle Poetas Españoles 3')

  await page.locator('#publish-street').fill('Avenida V Centenario 1')
  await page.locator('#publish-postcode').fill('38660')
  await page.evaluate(() => {
    const detail = {
      formattedAddress: 'Avenida V Centenario 1, 38660 Playa de las Américas, Santa Cruz de Tenerife, Spain',
      coordinates: { lat: 28.0674, lng: -16.7268 },
      addressComponents: [
        { long_name: 'Avenida V Centenario', types: ['route'] },
        { long_name: '1', types: ['street_number'] },
        { long_name: '38660', types: ['postal_code'] },
        { long_name: 'Playa de las Américas', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
    }
    window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail }))
    window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates: detail.coordinates } }))
  })

  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  expect(state.listingPatches?.at(-1)).toMatchObject({
    street: 'Avenida V Centenario 1',
    postcode: '38660',
    syncAddressGroup: true,
  })
  expect(await page.evaluate((key) => localStorage.getItem(key), `112233:listing-edit-draft:v1:${siblingId}`)).toBeNull()

  await page.goto(`/#/mis-anuncios/${siblingId}/editar`)
  await expect(page.locator('#publish-area')).toHaveValue('Playa de las Américas')
  await expect(page.locator('#publish-street')).toHaveValue('Avenida V Centenario 1')
  await expect(page.locator('#publish-postcode')).toHaveValue('38660')

  await page.goto(`/#/mis-anuncios/${independentId}/editar`)
  await expect(page.locator('#publish-street')).toHaveValue('Calle Poetas Españoles 9')
  await expect(page.locator('#publish-postcode')).toHaveValue('38678')
})

test('customer video: edit is not reported as saved when the server echoes a different private location', async ({ page }) => {
  const listingId = '33333333-3333-4333-8333-333333333333'
  const imageId = '22222222-2222-4222-8222-222222222222'
  const original = {
    ...lifecycleListing('published', listingId),
    street: 'Calle Poetas Españoles 3',
    postcode: '38678',
    exactLatitude: 28.0701,
    exactLongitude: -16.7318,
    latitude: 28.0708,
    longitude: -16.7322,
    imageUrls: requiredServerImageUrls(),
    coverImageUrl: requiredServerImageUrls()[0],
    description: 'Habitación de prueba con una descripción suficientemente larga para validar el formulario.',
  }
  const state: PublicationTestState = {
    mode: 'success',
    posts: 0,
    profilePatches: 0,
    listingPatches: [],
    mine: [original],
  }
  await mockPublicationApi(page, state)
  await page.route(`**/api/v1/listings/${listingId}`, async (route) => {
    if (route.request().method() !== 'PATCH') return route.fallback()
    state.listingPatches?.push(route.request().postDataJSON() as Record<string, unknown>)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(original) })
  })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:has-session', '1')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.reload()
  await page.goto(`/#/mis-anuncios/${listingId}/editar`)
  await expect(page.locator('#publish-street')).toBeVisible()
  await page.locator('#publish-street').fill('Avenida V Centenario 1')
  await page.locator('#publish-postcode').fill('38660')

  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click()

  await expect(page).toHaveURL(new RegExp(`#\\/mis-anuncios\\/${listingId}\\/editar$`))
  await expect(page.getByText('Cambios guardados')).toHaveCount(0)
  await expect(page.getByText(/servidor no confirmó la ubicación guardada/i)).toBeVisible()
})

test('publication contact validation matches the backend for hidden values and limits', async ({ page }) => {
  const state = { mode: 'success' as PublicationMode, posts: 0, profilePatches: 0 }
  await mockPublicationApi(page, state)
  await openCompletedPublicationForm(page)

  await page.locator('#publish-contact-phone').fill('not-a-phone')
  await page.getByRole('checkbox', { name: 'Mostrar teléfono' }).uncheck()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('Introduce un teléfono válido.')).toBeVisible()
  expect(state.posts).toBe(0)

  await page.locator('#publish-contact-phone').fill('1'.repeat(65))
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText('El teléfono no puede superar 64 caracteres.')).toBeVisible()
  expect(state.posts).toBe(0)

  await page.locator('#publish-contact-phone').fill(host.phone)
  await page.getByRole('checkbox', { name: 'Mostrar teléfono' }).check()
  await page.locator('#publish-contact-whatsapp').fill('')
  await page.getByRole('checkbox', { name: 'Mostrar WhatsApp' }).uncheck()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
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

test('stale owner response cannot cross an account switch', async ({ page }) => {
  let releaseFirstMine!: () => void
  const firstMineWait = new Promise<void>((resolve) => { releaseFirstMine = resolve })
  const privateA = { ...lifecycleListing('hidden'), title: 'Private listing account A', street: 'Private A street' }
  const privateB = { ...lifecycleListing('hidden', '55555555-5555-4555-8555-555555555555'), ownerUserId: secondHost.id, title: 'Private listing account B', street: 'Private B street' }
  const state: PublicationTestState = {
    mode: 'success', posts: 0, profilePatches: 0, authUser: host, loginUser: secondHost,
    mine: [privateA], mineWait: firstMineWait,
  }
  await mockPublicationApi(page, state)
  await page.addInitScript(() => localStorage.setItem('112233:has-session', '1'))
  await page.goto('/#/menu')
  await expect.poll(() => state.mineCalls ?? 0).toBe(1)

  await page.getByRole('button', { name: 'Cerrar sesión' }).click()
  state.mine = [privateB]
  state.mineWait = undefined
  await page.goto('/#/acceso')
  await page.getByRole('button', { name: 'Iniciar sesión con email' }).click()
  await page.getByLabel('Email').fill(secondHost.email)
  await page.getByLabel('Contraseña').fill('not-used-by-mock')
  await page.getByRole('button', { name: 'Iniciar sesión con email' }).click()
  await expect.poll(() => state.mineCalls ?? 0).toBeGreaterThanOrEqual(2)
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('main')).toContainText(privateB.title)

  releaseFirstMine()
  await page.waitForTimeout(100)
  await expect(page.locator('main')).not.toContainText(privateA.title)
  await expect(page.locator('main')).not.toContainText('Private A street')
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
