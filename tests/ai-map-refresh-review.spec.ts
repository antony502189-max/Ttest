import { expect, test, type Page } from '@playwright/test'

const sid = '00000000-0000-4000-8000-000000000011'
const ref = '00000000-0000-4000-8000-000000000012'
const hash = 'a'.repeat(64)
type Viewport = { north: number; south: number; east: number; west: number; zoom: number }

async function fixture(page: Page, lab: boolean, fault: string) {
  const point = lab ? { latitude: 28.09, longitude: -16.70 } : { latitude: 40.42, longitude: -3.70 }
  const intent = { schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: sid, version: 1,
    criteria: { budget: { strength: 'hard', value: { amount: '700.00', currency: 'EUR', period: 'monthly' } } } }
  const cards = { intent_hash: hash, cards: { total: 1, nextCursor: null, previousCursor: null,
    items: [{ id: 'synthetic-card', title: 'Synthetic', city: lab ? 'Adeje' : 'Madrid', area: 'Centro',
      rentalMode: 'long', price: 650, isExternal: true, sourceUrl: 'https://fixture.invalid/room', ...point }] } }
  const state = { queries: 0, refreshed: false, maps: [] as Viewport[], failMap: false, oldFinished: false }
  let releaseOld!: () => void
  const gate = new Promise<void>(resolve => { releaseOld = resolve })
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
    localStorage.setItem('112233:map-last-search-area:v2', JSON.stringify({ center: { lat: 28.12, lng: -16.72 }, savedAt: Date.now() }))
    // The stock SDK keeps fixed Tenerife bounds after setCenter. Supply a
    // bounded camera-dependent viewport here, so Madrid cannot render outside
    // the map's actual center/zoom. No production SDK behavior is changed.
    let current: typeof window.__googleMapsTestLastMap
    Object.defineProperty(window, '__googleMapsTestLastMap', {
      get: () => current,
      set: (map: NonNullable<typeof current>) => {
        current = map
        map.getBounds = () => {
          const center = map.getCenter(), span = 180 / 2 ** map.getZoom()
          return new google.maps.LatLngBounds()
            .extend({ lat: center.lat() - span, lng: center.lng() - span })
            .extend({ lat: center.lat() + span, lng: center.lng() + span }) as unknown as ReturnType<typeof map.getBounds>
        }
      },
    })
  })
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (url.hostname !== '127.0.0.1') return route.abort()
    if (path.endsWith('/ai-search/lab-runtime')) return route.fulfill({ json: {
      schema: 'ai-lab-runtime.v1', parser: 'decision-transport-fixture', source: 'a'.repeat(40),
      instance: '00000000-0000-4000-8000-000000000001', provider_transport: 'mock',
    } })
    if (path.endsWith('/capabilities')) return route.fulfill({ json: { text: true, map: true } })
    if (path.endsWith('/quota')) return route.fulfill({ json: { remaining: 2 } })
    if (path.endsWith('/identity')) return route.fulfill({ json: { ready: true } })
    if (path.endsWith('/listings/synthetic-card')) return route.fulfill({ json: {
      ...cards.cards.items[0], restrictions: [], amenities: [], imageUrls: [], owner: {}, availableFrom: null,
    } })
    if (path.endsWith('/sessions')) return route.fulfill({ json: { intent: { ...intent, version: 0 }, expires_at: '2099-01-01T00:00:00Z' } })
    if (path.endsWith(`/sessions/${sid}`)) return route.fulfill({ json: { intent, expires_at: '2099-01-01T00:00:00Z' } })
    if (path.endsWith('/query')) {
      state.queries++
      return route.fulfill({ json: { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 1 } }, cards } })
    }
    if (path.endsWith(`/results/${ref}`)) return route.fulfill({ json: { result_ref: ref, count: 1, intent_hash: hash, intent } })
    if (path.endsWith(`/results/${ref}/cards`)) {
      expect(request.postDataJSON()).toEqual({ search: { limit: 6 } })
      if (fault === 'cards-error') return route.fulfill({ status: 503, json: { detail: 'unavailable' } })
      state.refreshed = true
      state.failMap = fault === 'map-error'
      return route.fulfill({ json: cards })
    }
    if (path.endsWith(`/results/${ref}/map`)) {
      const body = request.postDataJSON()
      expect(Object.keys(body)).toEqual(['search'])
      expect(Object.keys(body.search).sort()).toEqual(['east', 'north', 'south', 'west', 'zoom'])
      const viewport = body.search as Viewport
      state.maps.push(viewport)
      const old = !state.refreshed
      if (old && fault === 'late') await gate
      if (state.failMap) { state.failMap = false; return route.fulfill({ status: 503, json: { detail: 'unavailable' } }) }
      const inside = point.latitude >= viewport.south && point.latitude <= viewport.north &&
        point.longitude >= viewport.west && point.longitude <= viewport.east
      await route.fulfill({ json: { intent_hash: state.refreshed && fault === 'mismatch' ? 'b'.repeat(64) : hash,
        map: { items: inside ? [{ type: 'listing', id: old ? 'old-source' : 'fresh-source', price: 650, promoted: false, ...point }] : [] } } }).catch(() => undefined)
      if (old) state.oldFinished = true
      return
    }
    if (path.startsWith('/api/')) return route.fulfill({ status: 404, json: {} })
    return route.continue()
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-rental-mode').selectOption('none')
  await page.locator('#ai-search-text').fill('Una habitación hasta 700 euros al mes')
  await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  const map = lab ? page.getByRole('region', { name: 'Локальная координатная карта' }) : page.locator('.ai-result-map')
  await expect.poll(() => state.maps.length).toBeGreaterThan(0)
  return { state, map, releaseOld }
}

for (const fault of ['success', 'cards-error', 'late', 'map-error', 'mismatch']) {
  test(`review viewport-sensitive refresh ${fault}`, async ({ page, baseURL }) => {
    const lab = baseURL?.endsWith(':4176') === true
    await page.setViewportSize({ width: 390, height: 1000 })
    const { state, map, releaseOld } = await fixture(page, lab, fault)
    if (fault !== 'late') await expect(map.locator('[data-listing-id="old-source"]')).toBeVisible()
    const mapHandle = lab ? await map.locator('svg').elementHandle() : await page.evaluateHandle(() => window.__googleMapsTestLastMap!)
    if (!lab) expect(await page.evaluate(() => {
      const center = window.__googleMapsTestLastMap!.getCenter()
      return { lat: center.lat(), lng: center.lng() }
    })).toEqual({ lat: 40.42, lng: -3.70 })
    if (lab) {
      await map.getByRole('button', { name: 'Масштаб 14' }).click()
      await map.getByRole('button', { name: 'Сдвинуть область' }).click()
    } else {
      await page.evaluate(() => { const map = window.__googleMapsTestLastMap!; map.setCenter({ lat: 40.421, lng: -3.701 }); map.getDiv().dispatchEvent(new WheelEvent('wheel')) })
    }
    const camera = lab ? null : await page.evaluate(() => {
      const map = window.__googleMapsTestLastMap!, center = map.getCenter()
      return { lat: center.lat(), lng: center.lng(), zoom: map.getZoom() }
    })
    await expect.poll(() => state.maps.at(-1)!.zoom).toBe(lab ? 15 : camera!.zoom)
    if (lab) await expect.poll(() => state.maps.at(-1)!.west).toBeCloseTo(-16.725)
    const before = state.maps.length, viewport = state.maps.at(-1)!
    if (!lab) expect(viewport).toEqual(await page.evaluate(() => {
      const map = window.__googleMapsTestLastMap!, bounds = map.getBounds(), ne = bounds.getNorthEast(), sw = bounds.getSouthWest()
      return { north: ne.lat(), east: ne.lng(), south: sw.lat(), west: sw.lng(), zoom: map.getZoom() }
    }))
    await page.getByRole('button', { name: 'Actualizar resultados sin gastar una búsqueda' }).click()
    if (fault === 'cards-error') {
      await expect(page.getByText('No se pudo cargar la página. Conservamos los últimos resultados.')).toBeVisible()
      expect(state.maps.length).toBe(before)
      await expect(map.locator('[data-listing-id="old-source"]')).toBeVisible()
    } else if (fault === 'map-error' || fault === 'mismatch') {
      await expect(map.locator('[data-listing-id]')).toHaveCount(0)
      const retry = map.getByRole('button', { name: lab ? 'Повторить загрузку карты' : 'Reintentar', exact: true })
      await expect(retry).toBeVisible()
      if (fault === 'map-error') {
        await retry.click()
        await expect(map.locator('[data-listing-id="fresh-source"]')).toBeVisible()
        expect(state.maps.length).toBe(before + 2)
      }
    } else {
      await expect(map.locator('[data-listing-id="fresh-source"]')).toBeVisible()
      releaseOld()
      await expect.poll(() => state.oldFinished).toBe(true)
      await expect(map.locator('[data-listing-id="old-source"]')).toHaveCount(0)
      expect(state.maps.length).toBe(before + 1)
    }
    expect(state.maps.at(-1)).toEqual(viewport)
    if (lab) {
      expect(await mapHandle!.evaluate(element => element.isConnected)).toBe(true)
      await expect(map.getByRole('button', { name: 'Масштаб 15' })).toBeVisible()
    } else {
      expect(await mapHandle!.evaluate(map => map === window.__googleMapsTestLastMap)).toBe(true)
      expect(await page.evaluate(() => { const map = window.__googleMapsTestLastMap!, center = map.getCenter(); return { lat: center.lat(), lng: center.lng(), zoom: map.getZoom() } })).toEqual(camera)
    }
    await page.getByRole('button', { name: 'Ver lista', exact: true }).click()
    await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
    await expect(map).toBeVisible()
    expect(state.queries).toBe(1)
    await expect(page.getByText('Búsquedas disponibles hoy: 2')).toBeVisible()
  })
}
