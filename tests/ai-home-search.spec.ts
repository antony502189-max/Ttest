import { expect, test, type Page } from '@playwright/test'

const sid = '00000000-0000-4000-8000-000000000001'
const ref = '00000000-0000-4000-8000-000000000002'
const requestText = 'En Madrid hasta 700 euros con mi gato'
const snapshot = (version: number) => ({ intent: { session_id: sid, version }, expires_at: '2099-01-01T00:00:00Z' })
const cards = (nextCursor: string | null = null) => ({ cards: { items: [], total: 0, nextCursor, previousCursor: null }, intent_hash: 'original-intent' })

async function setup(page: Page, enabled = true) {
  // Deny all nonlocal resources, and stub every API. These tests never touch
  // source sites, real provider APIs or an application database.
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.hostname !== '127.0.0.1') return route.abort()
    if (url.pathname === '/api/v1/ai-search/identity') return route.fulfill({ json: { ready: true } })
    if (url.pathname === '/api/v1/ai-search/capabilities') return route.fulfill({ json: { text: enabled, map: enabled, voice: false, saved_searches: false } })
    if (url.pathname.startsWith('/api/v1/media/')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="#eff5e5"/></svg>' })
    if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 404, json: { detail: 'Not found' } })
    return route.continue()
  })
  await page.addInitScript(() => { localStorage.setItem('112233:language:v1', 'es'); localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable') })
}

test('disabled runtime hides AI entry and preserves manual filters', async ({ page }) => {
  await setup(page, false)
  await page.goto('/#/')
  await expect(page.getByRole('button', { name: 'Escribir mi búsqueda' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Ver habitaciones', exact: true })).toBeVisible()
})

test('mobile reference panel, private text, zero confirmed results and followup version', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setup(page)
  let version = 0
  const messages: Record<string, unknown>[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(version) }))
  await page.route('**/api/v1/ai-search/query', async route => {
    expect(route.request().headers()['x-ai-request']).toBe('1')
    messages.push(route.request().postDataJSON())
    version++
    await route.fulfill({ json: { operation: { status: 'succeeded', remaining: 3 - version, receipt: { result_ref: ref, count: 0 } }, cards: cards() } })
  })
  await page.goto('/#/')
  await expect(page.getByRole('button', { name: 'Escribir mi búsqueda' })).toHaveCSS('background-color', 'rgb(201, 255, 39)')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByText('No encontramos opciones con todas las condiciones confirmadas.', { exact: false })).toBeVisible()
  await expect(page.getByText('Búsquedas disponibles hoy: 2')).toBeVisible()
  await page.getByLabel('¿Qué quieres cambiar?').fill('Y con balcón')
  await page.getByRole('button', { name: 'Actualizar búsqueda', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 1')).toBeVisible()
  expect(messages.map(message => message.expected_version)).toEqual([0, 1])
  expect(messages[0].text).toBe(requestText)
  expect(messages[0].idempotency_key).not.toBe(messages[1].idempotency_key)
  expect(await page.evaluate(text => JSON.stringify({ ...localStorage, ...sessionStorage }).includes(text), requestText)).toBe(false)
  expect(page.url()).not.toContain('Madrid')
  await page.screenshot({ path: 'output/ai-home-dialog-mobile.png', fullPage: true })
  const dialog = page.getByRole('dialog')
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  await page.getByRole('button', { name: 'Volver a los filtros' }).click()
  await expect(dialog).toBeHidden()
  await page.screenshot({ path: 'output/ai-home-panel-mobile.png', fullPage: true })
  await page.locator('.home-ai-search').screenshot({ path: 'output/ai-home-panel-detail.png' })
})

test('lost response and running attempt reuse exact key/text even with zero remaining', async ({ page }) => {
  await setup(page)
  const messages: unknown[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/query', async route => {
    messages.push(route.request().postDataJSON())
    if (messages.length === 1) return route.abort('failed')
    if (messages.length === 2) return route.fulfill({ json: { operation: { status: 'running', remaining: 0, receipt: null }, cards: null } })
    return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 0, receipt: { result_ref: ref, count: 0 } }, cards: cards() } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  const retry = page.getByRole('button', { name: 'Comprobar el mismo intento' })
  await expect(retry).toBeEnabled()
  await expect(page.getByLabel('Cuéntanos qué necesitas')).toBeDisabled()
  await retry.click()
  await expect(page.getByText('La búsqueda sigue en curso.', { exact: false })).toBeVisible()
  await expect(retry).toBeEnabled()
  await retry.click()
  await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeDisabled()
  expect(messages).toHaveLength(3)
  expect(messages[1]).toEqual(messages[0])
  expect(messages[2]).toEqual(messages[0])
})

test('terminal conflict resyncs session and requires deliberate resubmission', async ({ page }) => {
  await setup(page)
  const versions: number[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(4) }))
  await page.route('**/api/v1/ai-search/query', route => {
    versions.push(route.request().postDataJSON().expected_version)
    return route.fulfill({ json: { operation: { status: 'failed', failure_code: 'SESSION_VERSION_CONFLICT', remaining: 3, receipt: null }, cards: null } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByText('La búsqueda cambió.', { exact: false })).toBeVisible()
  expect(versions).toEqual([0])
  await expect(page.getByLabel('Cuéntanos qué necesitas')).toBeEnabled()
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect.poll(() => versions.length).toBe(2)
  expect(versions).toEqual([0, 4])
})

test('pages use original result reference and never submit another message', async ({ page }) => {
  await setup(page)
  let messages = 0
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages++
    return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards('signed-cursor') } })
  })
  let pages = 0
  const cursors: Array<string | undefined> = []
  await page.route(`**/api/v1/ai-search/results/${ref}/cards`, route => {
    const body = route.request().postDataJSON()
    expect(body.search.limit).toBe(6)
    cursors.push(body.search.cursor)
    pages++
    return route.fulfill({ json: cards() })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
  expect(messages).toBe(1)
  expect(pages).toBe(1)
  await expect(page.getByText('Los anuncios y su orden pueden cambiar entre páginas.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Actualizar resultados sin gastar una búsqueda' }).click()
  await expect.poll(() => pages).toBe(2)
  expect(cursors).toEqual(['signed-cursor', undefined])
  expect(messages).toBe(1)
})

test('confirmed cards preserve server TOP order, native gallery recovery and external destination', async ({ page }) => {
  await setup(page)
  const native = {
    id: '00000000-0000-4000-8000-000000000003', title: 'Habitación TOP confirmada', city: 'Madrid', area: 'Centro',
    approximateAddress: 'Centro', rentalMode: 'long', price: 650, roomType: 'Individual', currentResidents: 1,
    roomCapacity: 1, roomSizeM2: 14, availableFrom: null, billsIncluded: true, restrictions: [],
    advertiserType: 'Particular', isExternal: false, sourceUrl: null, primarySource: null, sourcePriceText: null,
    pricePeriod: 'month', priceIsFrom: false, publishedAt: '2026-10-27', promoted: true,
    coverImageUrl: '/api/v1/media/cover.webp', description: 'Condiciones confirmadas',
  }
  const external = { ...native, id: '00000000-0000-4000-8000-000000000004', title: 'Habitación externa confirmada',
    isExternal: true, promoted: false, sourceUrl: 'https://example.org/room', primarySource: 'Example' }
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 2 } },
    cards: { ...cards(), budget_prices: [{ listing_id: native.id, matched_amount: 200, matched_period: 'weekly',
      display_amount: 650, display_period: 'monthly', currency: 'EUR', confirmation: 'current_source_proof' }],
      cards: { ...cards().cards, items: [native, external], total: 2 } },
  } }))
  let recovery = 0
  await page.route(`**/api/v1/listings/${native.id}/images`, route => {
    recovery++
    return route.fulfill({ json: [0, 1, 2].map(index => ({ assetId: String(index), url: `/api/v1/media/gallery-${index}.webp`, sortOrder: index, isCover: index === 0 })) })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  const rows = page.getByRole('dialog').locator('[data-listing-id]')
  await expect(page.getByText('Precio confirmado para tu presupuesto: 200 € por semana')).toBeVisible()
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toHaveAttribute('data-listing-id', native.id)
  await expect.poll(() => recovery).toBeGreaterThan(0)
  await expect(rows.first().locator('img').first()).toHaveAttribute('src', /gallery-0/)
  await expect(rows.last().locator('a[href="https://example.org/room"]').first()).toBeVisible()
  await page.getByRole('dialog').screenshot({ path: 'output/pr394-budget-period-detail.png' })
})

test('body rejection allows editing without replaying an unreserved operation', async ({ page }) => {
  await setup(page)
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ status: 413, json: { detail: 'AI_REQUEST_BODY_TOO_LARGE' } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByText('Acorta o revisa el texto antes de enviarlo de nuevo.')).toBeVisible()
  await expect(page.getByLabel('Cuéntanos qué necesitas')).toBeEnabled()
})

test('reopening reads current quota without creating a session or charging another message', async ({ page }) => {
  await setup(page)
  let remaining = 3
  let messages = 0
  let sessions = 0
  await page.route('**/api/v1/ai-search/sessions', route => { sessions++; return route.fulfill({ json: snapshot(0) }) })
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/quota', route => route.fulfill({ json: { remaining } }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages++
    remaining = 0
    return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 0, receipt: { result_ref: ref, count: 0 } }, cards: cards() } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 0')).toBeVisible()
  await page.getByRole('button', { name: 'Volver a los filtros' }).click()
  remaining = 3
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 3')).toBeVisible()
  expect(sessions).toBe(1)
  expect(messages).toBe(1)
})

test('verified map uses original result and viewport only, preserving promotions without another debit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await setup(page)
  let messages = 0
  let legacyMaps = 0
  const viewports: Record<string, number>[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/listings/map', route => { legacyMaps++; return route.fulfill({ json: { items: [] } }) })
  await page.route('**/api/v1/ai-search/query', route => {
    messages++
    return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 2 } }, cards: { ...cards(), cards: { ...cards().cards, total: 2 } } } })
  })
  await page.route(`**/api/v1/ai-search/results/${ref}/map`, route => {
    const body = route.request().postDataJSON()
    expect(Object.keys(body)).toEqual(['search'])
    expect(Object.keys(body.search).sort()).toEqual(['east', 'north', 'south', 'west', 'zoom'])
    expect(route.request().headers()['x-ai-request']).toBe('1')
    viewports.push(body.search)
    return route.fulfill({ json: { intent_hash: 'original-intent', map: { items: [
      { type: 'listing', id: 'verified-top', latitude: 28.12, longitude: -16.72, price: 650, promoted: true, isExternal: true, sourceUrl: 'https://example.org/room' },
      { type: 'cluster', id: 'verified-cluster', latitude: 28.15, longitude: -16.71, count: 5, promoted: false },
    ] } } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  const map = page.locator('.ai-result-map')
  await expect(map.locator('.google-map-canvas')).toHaveAttribute('data-map-instance', 'google-ready')
  await expect(map.locator('[data-listing-id="verified-top"]')).toHaveAttribute('data-promoted', 'true')
  await expect(map.locator('.map-cluster-marker-shell')).toHaveCount(1)
  expect(viewports.length).toBeGreaterThan(0)
  expect(messages).toBe(1)
  expect(legacyMaps).toBe(0)
  await map.screenshot({ path: 'output/ai-home-result-map.png' })
  expect(await page.getByRole('dialog').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  expect(await page.getByRole('dialog').evaluate(element => Number(getComputedStyle(element).zIndex))).toBeGreaterThan(100)
})

test('map rejects a different intent hash and never falls back to manual catalog', async ({ page }) => {
  await setup(page)
  let legacyMaps = 0
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/listings/map', route => { legacyMaps++; return route.fulfill({ json: { items: [] } }) })
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards(),
  } }))
  await page.route(`**/api/v1/ai-search/results/${ref}/map`, route => route.fulfill({ json: {
    intent_hash: 'different-intent', map: { items: [{ type: 'listing', id: 'must-not-render', latitude: 28, longitude: -16, price: 1 }] },
  } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  await expect(page.getByText('No se pudieron cargar los anuncios del mapa.', { exact: false })).toBeVisible()
  await expect(page.locator('.ai-result-map .map-price-marker-shell')).toHaveCount(0)
  expect(legacyMaps).toBe(0)
})

test('late map response from an earlier result cannot replace a followup map', async ({ page }) => {
  await setup(page)
  const nextRef = '00000000-0000-4000-8000-000000000005'
  let version = 0
  let oldRequested = false
  let oldFinished = false
  let releaseOld!: () => void
  const gate = new Promise<void>(resolve => { releaseOld = resolve })
  const marker = (id: string) => ({ type: 'listing', id, latitude: 28.12, longitude: -16.72, price: 650, promoted: false, isExternal: false, sourceUrl: null })
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(version) }))
  await page.route('**/api/v1/ai-search/query', route => {
    version++
    return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 3 - version, receipt: { result_ref: version === 1 ? ref : nextRef, count: 0 } }, cards: cards() } })
  })
  await page.route(`**/api/v1/ai-search/results/${ref}/map`, async route => {
    oldRequested = true
    await gate
    await route.fulfill({ json: { intent_hash: 'original-intent', map: { items: [marker('old-marker')] } } }).catch(() => undefined)
    oldFinished = true
  })
  await page.route(`**/api/v1/ai-search/results/${nextRef}/map`, route => route.fulfill({ json: {
    intent_hash: 'original-intent', map: { items: [marker('new-marker')] },
  } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  await expect.poll(() => oldRequested).toBe(true)
  await page.getByLabel('¿Qué quieres cambiar?').fill('También una terraza')
  await page.getByRole('button', { name: 'Actualizar búsqueda', exact: true }).click()
  await expect(page.locator('.ai-result-map [data-listing-id="new-marker"]')).toHaveCount(1)
  releaseOld()
  await expect.poll(() => oldFinished).toBe(true)
  await expect(page.locator('.ai-result-map [data-listing-id="old-marker"]')).toHaveCount(0)
  await expect(page.locator('.ai-result-map [data-listing-id="new-marker"]')).toHaveCount(1)
})
for (const terminal of ['expired', 'not-found', 'guest-expired', 'replayed-success'] as const) {
  test(`terminal ${terminal} settles before expired session refresh and permits explicit new identity`, async ({ page }) => {
    await setup(page)
    const nextSid = '00000000-0000-4000-8000-000000000099'
    const messages: Record<string, unknown>[] = []
    let creates = 0
    await page.route('**/api/v1/ai-search/sessions', route => {
      creates++
      return route.fulfill({ json: { ...snapshot(0), intent: { ...snapshot(0).intent, session_id: creates === 1 ? sid : nextSid } } })
    })
    await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({
      status: terminal === 'guest-expired' ? 401 : terminal === 'not-found' ? 404 : 409,
      json: { detail: terminal === 'guest-expired' ? 'AI_GUEST_IDENTITY_INVALID_OR_EXPIRED' : terminal === 'not-found' ? 'SESSION_NOT_FOUND' : 'SESSION_EXPIRED' },
    }))
    await page.route(`**/api/v1/ai-search/sessions/${nextSid}`, route => route.fulfill({ json: {
      ...snapshot(1), intent: { ...snapshot(1).intent, session_id: nextSid },
    } }))
    await page.route('**/api/v1/ai-search/query', route => {
      messages.push(route.request().postDataJSON())
      if (terminal === 'replayed-success' && messages.length === 1) return route.abort('failed')
      const success = terminal === 'replayed-success' || creates === 2
      return route.fulfill({ json: { operation: { status: success ? 'succeeded' : 'failed',
        failure_code: success ? null : 'SESSION_EXPIRED', remaining: 2,
        receipt: success ? { result_ref: ref, count: 0 } : null }, cards: success ? cards() : null } })
    })
    await page.goto('/#/')
    await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
    await page.getByLabel('Cuéntanos qué necesitas').fill(requestText)
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    if (terminal === 'replayed-success') {
      await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeDisabled()
      await page.getByRole('button', { name: 'Comprobar el mismo intento' }).click()
      expect(messages[1]).toEqual(messages[0])
    }
    await expect(page.getByText('El intento terminó, pero el diálogo no está disponible.', { exact: false })).toBeVisible()
    await expect(page.locator('#ai-search-text')).toBeEnabled()
    await expect(page.getByRole('button', { name: 'Comprobar el mismo intento' })).toHaveCount(0)
    expect(creates).toBe(1)
    if (terminal === 'replayed-success') await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
    await page.getByRole('button', { name: 'Iniciar nueva conversación' }).click()
    await expect(page.locator('#ai-search-text')).toHaveValue(terminal === 'replayed-success' ? '' : requestText)
    await page.locator('#ai-search-text').fill('Una búsqueda nueva')
    await page.getByRole('button', { name: terminal === 'replayed-success' ? 'Actualizar búsqueda' : 'Buscar habitaciones', exact: true }).click()
    await expect.poll(() => creates).toBe(2)
    await expect.poll(() => messages.length).toBe(terminal === 'replayed-success' ? 3 : 2)
    const fresh = messages.at(-1)!
    expect(fresh.session_id).toBe(nextSid)
    expect(fresh.expected_version).toBe(0)
    expect(fresh.idempotency_key).not.toBe(messages[0].idempotency_key)
    expect(fresh.text).toBe('Una búsqueda nueva')
  })
}

for (const failure of ['503', '429', 'network', 'timeout'] as const) {
  test(`transient refresh ${failure} retains draft, identity and resynchronizes version`, async ({ page }) => {
    await setup(page)
    const messages: Record<string, unknown>[] = []
    let reads = 0
    await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
    await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => {
      if (++reads > 1) return route.fulfill({ json: snapshot(7) })
      if (failure === 'network') return route.abort('failed')
      if (failure === 'timeout') return new Promise(() => {})
      return route.fulfill({ status: Number(failure), json: { detail: 'AI_SERVICE_UNAVAILABLE' } })
    })
    await page.route('**/api/v1/ai-search/query', route => {
      messages.push(route.request().postDataJSON())
      return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards('cursor') } })
    })
    await page.goto('/#/')
    await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
    await page.locator('#ai-search-text').fill(requestText)
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    await expect(page.locator('#ai-search-text')).toBeEnabled()
    await page.locator('#ai-search-text').fill('Con balcón')
    await expect(page.getByRole('button', { name: 'Reintentar sincronización' })).toBeEnabled({ timeout: 20000 })
    await expect(page.getByText('No se pudo actualizar el diálogo.', { exact: false })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Reintentar sincronización' }).click()
    await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeEnabled()
    await expect(page.locator('#ai-search-text')).toHaveValue('Con balcón')
    await page.getByRole('button', { name: 'Actualizar búsqueda', exact: true }).click()
    await expect.poll(() => messages.length).toBe(2)
    expect(messages[1].session_id).toBe(sid)
    expect(messages[1].expected_version).toBe(7)
  })
}

test('slow refresh frees draft and card navigation while guarding version-sensitive actions', async ({ page }) => {
  await setup(page)
  let release!: () => void
  const wait = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, async route => { await wait; await route.fulfill({ json: snapshot(1) }) })
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards('cursor'),
  } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
  await expect(page.locator('#ai-search-text')).toBeEnabled()
  await page.locator('#ai-search-text').fill('Un borrador nuevo')
  await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeEnabled()
})

for (const expireOn of ['refresh', 'page', 'receipt'] as const) {
  test(`expiry on ${expireOn} disables paging or settles receipt without cards`, async ({ page }) => {
    await setup(page)
    await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
    await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => expireOn === 'refresh'
      ? route.fulfill({ status: 409, json: { detail: 'SESSION_EXPIRED' } }) : route.fulfill({ json: snapshot(1) }))
    await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
      operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } },
      cards: expireOn === 'receipt' ? null : cards('signed-cursor'),
      cards_error: expireOn === 'receipt' ? 'RESULT_EXPIRED_REQUERY_REQUIRED' : null,
    } }))
    await page.route(`**/api/v1/ai-search/results/${ref}/cards`, route => route.fulfill({ status: 409, json: { detail: 'RESULT_EXPIRED_REQUERY_REQUIRED' } }))
    await page.goto('/#/')
    await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
    await page.locator('#ai-search-text').fill(requestText)
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    if (expireOn === 'page') await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(page.getByText(expireOn === 'refresh' ? 'El intento terminó, pero el diálogo no está disponible.' : 'Los resultados ya no están disponibles.', { exact: false })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
    await expect(page.getByRole('button', { name: 'Comprobar el mismo intento' })).toHaveCount(0)
    if (expireOn !== 'receipt') {
      await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
      await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
    } else await expect(page.locator('#ai-search-text')).toHaveValue(requestText)
  })
}

test('explicit live resets use current version, preserve draft and cards, and survive server failure', async ({ page }) => {
  await setup(page)
  let creates = 0
  let resets = 0
  const nextSid = '00000000-0000-4000-8000-000000000099'
  await page.route('**/api/v1/ai-search/sessions', route => { creates++; return route.fulfill({ json: snapshot(0) }) })
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/sessions/*/reset', route => {
    expect(route.request().postDataJSON()).toMatchObject({ expected_version: resets === 0 ? 1 : 0 })
    expect(route.request().postDataJSON().idempotency_key).toBeTruthy()
    resets++
    if (resets === 3) return route.fulfill({ status: 429, json: { detail: 'SESSION_LIMIT' } })
    return route.fulfill({ json: { ...snapshot(0), intent: { session_id: nextSid, version: 0 } } })
  })
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards(),
  } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
  const draft = 'Condiciones privadas largas '.repeat(500)
  await page.locator('#ai-search-text').fill(draft)
  for (let n = 1; n <= 3; n++) {
    await page.getByRole('button', { name: 'Iniciar nueva conversación' }).click()
    await expect.poll(() => resets).toBe(n)
    await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
    await expect(page.locator('#ai-search-text')).toHaveValue(draft)
    await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
  }
  expect(creates).toBe(1)
  await expect(page.getByText('Hay demasiadas conversaciones activas.', { exact: false })).toBeVisible()
})

test('expired create failure keeps draft and zero quota refreshes on reopen without an owned session', async ({ page }) => {
  await setup(page)
  let remaining = 3
  let creates = 0
  await page.route('**/api/v1/ai-search/quota', route => route.fulfill({ json: { remaining } }))
  await page.route('**/api/v1/ai-search/sessions', route => ++creates === 1
    ? route.fulfill({ json: snapshot(0) }) : route.fulfill({ status: 503, json: { detail: 'AI_SERVICE_UNAVAILABLE' } }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ status: 409, json: { detail: 'SESSION_EXPIRED' } }))
  await page.route('**/api/v1/ai-search/query', route => {
    remaining = 0
    return route.fulfill({ json: { operation: { status: 'failed', remaining: 0, failure_code: 'SESSION_EXPIRED', receipt: null }, cards: null } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
  await page.getByRole('button', { name: 'Iniciar nueva conversación' }).click()
  await expect(page.getByText('No se pudo iniciar una nueva conversación.', { exact: false })).toBeVisible()
  await expect(page.locator('#ai-search-text')).toHaveValue(requestText)
  await page.getByRole('button', { name: 'Volver a los filtros' }).click()
  remaining = 3
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 3')).toBeVisible()
})


test('quota refresh works before a session exists after the day changes', async ({ page }) => {
  await setup(page)
  let remaining = 0
  let creates = 0
  await page.route('**/api/v1/ai-search/quota', route => route.fulfill({ json: { remaining } }))
  await page.route('**/api/v1/ai-search/sessions', route => { creates++; return route.fulfill({ json: snapshot(0) }) })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await expect(page.getByText('Búsquedas disponibles hoy: 0')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buscar habitaciones', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Volver a los filtros' }).click()
  remaining = 3
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await expect(page.getByRole('button', { name: 'Buscar habitaciones', exact: true })).toBeEnabled()
  expect(creates).toBe(0)
})


test('an ambiguous HTTP 409 preserves the exact pending operation', async ({ page }) => {
  await setup(page)
  const messages: unknown[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages.push(route.request().postDataJSON())
    return route.fulfill({ status: 409, json: { detail: 'AI_OPERATION_UNAVAILABLE' } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Comprobar el mismo intento' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeDisabled()
  await page.getByRole('button', { name: 'Comprobar el mismo intento' }).click()
  await expect.poll(() => messages.length).toBe(2)
  expect(messages[1]).toEqual(messages[0])
})


for (const code of ['AI_GUEST_IDENTITY_INVALID_OR_EXPIRED', 'AI_GUEST_IDENTITY_REQUIRED']) {
  test(`query 401 ${code} releases old-owner pending and keeps editable draft`, async ({ page }) => {
    await setup(page)
    const sent: Record<string, unknown>[] = []
    let creates = 0
    await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: {
      ...snapshot(0), intent: { session_id: `${sid.slice(0, -1)}${++creates}`, version: 0 },
    } }))
    await page.route('**/api/v1/ai-search/sessions/*', route => route.fulfill({ json: snapshot(1) }))
    await page.route('**/api/v1/ai-search/query', route => {
      sent.push(route.request().postDataJSON())
      return sent.length === 1 ? route.fulfill({ status: 401, json: { detail: code } })
        : route.fulfill({ json: { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards() } })
    })
    await page.goto('/#/')
    await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
    await page.locator('#ai-search-text').fill(requestText)
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    await expect(page.locator('#ai-search-text')).toBeEnabled()
    await expect(page.locator('#ai-search-text')).toHaveValue(requestText)
    await expect(page.getByRole('button', { name: 'Comprobar el mismo intento' })).toHaveCount(0)
    await page.getByRole('button', { name: 'Iniciar nueva conversación' }).click()
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    await expect.poll(() => sent.length).toBe(2)
    expect(sent[1].session_id).not.toBe(sent[0].session_id)
    expect(sent[1].idempotency_key).not.toBe(sent[0].idempotency_key)
  })
}

test('hard quota rejection releases unreserved pending and recovers on authoritative rollover', async ({ page }) => {
  await setup(page)
  let remaining = 3
  let messages = 0
  await page.route('**/api/v1/ai-search/quota', route => route.fulfill({ json: { remaining } }))
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages++; remaining = 0
    return route.fulfill({ status: 429, json: { detail: 'QUOTA_EXHAUSTED' } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.locator('#ai-search-text')).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
  await expect(page.getByText('Búsquedas disponibles hoy: 0')).toBeVisible()
  await page.getByRole('button', { name: 'Volver a los filtros' }).click()
  remaining = 3
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await expect(page.getByRole('button', { name: 'Buscar habitaciones', exact: true })).toBeEnabled()
  expect(messages).toBe(1)
})

for (const problem of ['AI_REQUERY_REQUIRED', 'RESULT_NOT_FOUND', 'hash-mismatch']) {
  test(`paging ${problem} invalidates only results and preserves live conversation`, async ({ page }) => {
    await setup(page)
    await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
    await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
    await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
      operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards('old-cursor'),
    } }))
    await page.route(`**/api/v1/ai-search/results/${ref}/cards`, route => problem === 'hash-mismatch'
      ? route.fulfill({ json: { ...cards('bad-cursor'), intent_hash: 'another-intent' } })
      : route.fulfill({ status: problem === 'RESULT_NOT_FOUND' ? 404 : 409, json: { detail: problem } }))
    await page.goto('/#/')
    await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
    await page.locator('#ai-search-text').fill(requestText)
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    await page.locator('#ai-search-text').fill('Con balcón')
    await page.getByRole('button', { name: 'Siguiente', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
    await expect(page.getByText('Los resultados ya no están disponibles.', { exact: false })).toBeVisible()
    await expect(page.locator('#ai-search-text')).toHaveValue('Con balcón')
    await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeEnabled()
  })
}

test('missing cards on terminal receipt resyncs a live session instead of discarding it', async ({ page }) => {
  await setup(page)
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(5) }))
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: null, cards_error: 'RESULT_NOT_FOUND',
  } }))
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByText('Los resultados ya no están disponibles.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Buscar habitaciones', exact: true })).toBeEnabled()
  await expect(page.locator('#ai-search-text')).toHaveValue(requestText)
})


test('lost reset acknowledgement blocks old paging and preserves the lifecycle key', async ({ page }) => {
  await setup(page)
  const attempts: Record<string, unknown>[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/query', route => route.fulfill({ json: {
    operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: cards('old-cursor'),
  } }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}/reset`, route => {
    attempts.push(route.request().postDataJSON())
    return attempts.length === 1 ? route.abort('failed') : route.fulfill({ json: {
      ...snapshot(0), intent: { session_id: 'recovered-session', version: 0 },
    } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  const reset = page.getByRole('button', { name: 'Iniciar nueva conversación' })
  await expect(reset).toBeEnabled()
  await page.locator('#ai-search-text').fill('Con balcón')
  await reset.click()
  await expect(page.getByText('No se pudo iniciar una nueva conversación.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Actualizar búsqueda', exact: true })).toBeDisabled()
  await reset.click()
  await expect(page.getByText('Nueva conversación lista.', { exact: false })).toBeVisible()
  expect(attempts[1]).toEqual(attempts[0])
  await expect(page.locator('#ai-search-text')).toHaveValue('Con balcón')
})

test('unsettled query blocks stale paging but its exact replay remains available', async ({ page }) => {
  await setup(page)
  const messages: unknown[] = []
  await page.route('**/api/v1/ai-search/sessions', route => route.fulfill({ json: snapshot(0) }))
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages.push(route.request().postDataJSON())
    return route.fulfill({ json: { operation: { status: messages.length === 1 ? 'succeeded' : 'running', remaining: 2,
      receipt: messages.length === 1 ? { result_ref: ref, count: 0 } : null }, cards: messages.length === 1 ? cards('old-cursor') : null } })
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-search-text').fill(requestText)
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Iniciar nueva conversación' })).toBeEnabled()
  await page.locator('#ai-search-text').fill('Con balcón')
  await page.getByRole('button', { name: 'Actualizar búsqueda', exact: true }).click()
  const replay = page.getByRole('button', { name: 'Comprobar el mismo intento' })
  await expect(replay).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Siguiente', exact: true })).toBeDisabled()
  await replay.click()
  await expect.poll(() => messages.length).toBe(3)
  expect(messages[2]).toEqual(messages[1])
})
