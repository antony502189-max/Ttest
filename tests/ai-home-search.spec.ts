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
  await page.route(`**/api/v1/ai-search/results/${ref}/cards`, route => {
    expect(route.request().postDataJSON()).toEqual({ search: { limit: 6, cursor: 'signed-cursor' } })
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
  let remaining = 0
  let messages = 0
  let sessions = 0
  await page.route('**/api/v1/ai-search/sessions', route => { sessions++; return route.fulfill({ json: snapshot(0) }) })
  await page.route(`**/api/v1/ai-search/sessions/${sid}`, route => route.fulfill({ json: snapshot(1) }))
  await page.route('**/api/v1/ai-search/quota', route => route.fulfill({ json: { remaining } }))
  await page.route('**/api/v1/ai-search/query', route => {
    messages++
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
