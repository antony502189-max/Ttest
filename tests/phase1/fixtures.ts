import type { Page, Route } from '@playwright/test'

export const id = '20000000-0000-4000-8000-000000000001'
export const urls = Array.from({ length: 15 }, (_, i) => `/api/v1/media/00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`)
export const rows = (count: number) => urls.slice(0, count).map((url, i) => ({ assetId: url.split('/').pop(), url, sortOrder: i, isCover: i === 0 }))
export function deferred() {
  let resolve!: () => void
  const promise = new Promise<void>((r) => { resolve = r })
  return { promise, resolve }
}
export function card(count = 1, listingId = id, rentalMode = 'holiday', external = false) {
  return { id: listingId, title: `Galería ${listingId}`, city: 'Adeje', area: 'Playa', approximateAddress: 'Ubicación aproximada', rentalMode,
    price: 55, roomType: 'Habitación individual', currentResidents: 1, roomCapacity: 1, bedroomCount: 2, roomSizeM2: 14,
    availableFrom: '2026-10-01', billsIncluded: true, restrictions: [], advertiserType: 'Particular', isExternal: external,
    sourceUrl: null, primarySource: null, publishedAt: '2026-09-30T00:00:00Z', promoted: false, coverImageUrl: urls[0], imageUrls: urls.slice(0, count), description: 'Galería fixture' }
}
export function detail(rentalMode = 'holiday') {
  return { ...card(5, id, rentalMode), ownerUserId: id, owner: { name: 'Fixture', initials: 'FX', since: null, response: '', verified: true }, amenities: [],
    status: 'published', cadence: rentalMode === 'holiday' ? 'noche' : 'mes', availableUntil: null, minimumStayMonths: 1, minimumNights: 1,
    expiresAt: '2099-01-01', views: 0, showPhone: false, showWhatsApp: false }
}
export function result(items = [card()], nextCursor: string | null = null, total = items.length) { return { items, total, nextCursor, previousCursor: null } }
export type SearchBody = { rentalMode: string; query: string; cursor?: string; limit: number; sort: string; favoriteIds?: string[] }
export async function fixtures(page: Page, search: (body: SearchBody, route: Route) => Promise<void>, gallery: (route: Route) => Promise<void> = (route) => route.fulfill({ json: rows(5) })) {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => { localStorage.setItem('112233:mobile-onboarding:v1', 'done'); localStorage.setItem('112233:language:v1', 'es') })
  await page.route('**/api/v1/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.endsWith('/search/cards')) return search(route.request().postDataJSON() as SearchBody, route)
    if (pathname.endsWith('/images')) return gallery(route)
    if (pathname.startsWith('/api/v1/media/')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#789"/></svg>' })
    if (pathname === `/api/v1/listings/${id}`) return route.fulfill({ json: detail() })
    if (pathname.endsWith('/catalog-version')) return route.fulfill({ json: { version: '1', updatedAt: '2026-10-08T00:00:00Z' } })
    if (pathname.endsWith('/auth/refresh')) return route.fulfill({ status: 401, json: {} })
    if (pathname.endsWith('/homepage-hero')) return route.fulfill({ json: null })
    return route.fulfill({ json: [] })
  })
  return errors
}
export const changeSearch = (page: Page, query: string) => page.evaluate(query => { location.hash = `#/buscar?${query}` }, query)
