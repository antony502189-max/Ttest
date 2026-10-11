import { expect, test } from '@playwright/test'
import { mobileResultBadges } from '../src/lib/mobile-result-badges'
import { buildListingSearchBody } from '../src/api/listings'
import { defaultFilters } from '../src/data/listings'
import { filtersFromParams, filtersToParams } from '../src/lib/search'
import { searchGeographyFromParams } from '../src/lib/search-geography'
import type { Filters, Listing } from '../src/types'

const instance = (requirements: string[], capacity: number | null): Pick<Listing, 'restrictions' | 'roomCapacity'> => ({
  restrictions: requirements,
  roomCapacity: capacity,
})

test('same actual conditions produce two badges in Spanish, Russian and English', () => {
  const listing = instance(['Solo hombre', 'Habitación para 1 persona'], 1)
  for (const locale of ['es', 'ru', 'en'] as const) {
    const result = mobileResultBadges(listing, locale)
    expect(result, locale).toHaveLength(2)
    expect(result[0]).not.toEqual(result[1])
    expect(result.join(' ')).toMatch(/1\s+(persona|person|человека)/u)
  }
})

test('legacy abbreviated capacity strings and repeated translations never create a third pill', () => {
  const variants = ['1 persona', 'Habitación para 1 persona', 'Room for 1 person', 'Комната для 1 чел.']
  for (const locale of ['es', 'ru', 'en'] as const) {
    for (const variant of variants) {
      expect(mobileResultBadges(instance(['Solo hombre', variant], 1), locale)).toHaveLength(2)
    }
  }
  // Distinct restrictions must be retained; no arbitrary 2-badge truncation.
  expect(mobileResultBadges(instance(['Solo hombre', 'Sin mascotas'], 1), 'ru')).toHaveLength(3)
})

test('search geography and all filter values depend on URL, never the display locale', () => {
  const canaries = new URLSearchParams('q=Canarias&comunidad=05&alquiler=long&precioMax=650')
  const spain = new URLSearchParams('q=España&alquiler=long&precioMax=650')
  expect(searchGeographyFromParams(canaries)).toEqual({ query: 'Canarias', autonomousCommunity: '05' })
  expect(searchGeographyFromParams(spain)).toEqual({ query: 'España', autonomousCommunity: undefined })
  expect(searchGeographyFromParams(canaries)).not.toEqual(searchGeographyFromParams(spain))
  for (const language of ['es', 'ru', 'en'] as const) {
    // The locale has no place in the API query or filter state.
    expect(buildListingSearchBody({
      rentalMode: 'long', ...searchGeographyFromParams(canaries),
      filters: filtersFromParams(canaries), minPrice: 0, maxPrice: 650,
    })).toMatchObject({ query: 'Canarias', autonomousCommunity: '05', maxPrice: 650 })
    expect(language).toMatch(/es|ru|en/)
  }
})

test('advanced filters survive the URL serializer and are sent to production API', () => {
  const filters: Filters = {
    ...defaultFilters,
    areas: [], conditions: [], amenities: ['Terraza', 'Piscina'], tenantRequirements: ['single-man', 'single-woman'],
    acceptedTenantTypes: ['man', 'woman'],
    minPrice: 100, maxPrice: 650,
    available: '2026-11-01', availableUntil: '2026-12-01',
    shower: 'Ducha privada', toilet: 'Aseo privado', kitchen: 'Cocina privada',
    smoking: 'No', pets: 'Sí', accessible: 'Sí', floor: '2',
    roomCapacity: '1', bedType: 'single',
  }
  const params = filtersToParams(filters, new URLSearchParams('q=España&comunidad=05'))
  const roundtrip = filtersFromParams(params)
  expect(roundtrip.tenantRequirements).toEqual(['single-man', 'single-woman'])
  expect(roundtrip.amenities).toEqual(['Terraza', 'Piscina'])
  const body = buildListingSearchBody({
    rentalMode: 'long', ...searchGeographyFromParams(params),
    filters: roundtrip, minPrice: roundtrip.minPrice, maxPrice: roundtrip.maxPrice,
  })
  expect(body).toMatchObject({
    query: 'España', autonomousCommunity: '05', minPrice: 100, maxPrice: 650,
    availableFrom: '2026-11-01', availableUntil: '2026-12-01',
    shower: 'Ducha privada', toilet: 'Aseo privado', kitchen: 'Cocina privada',
    smokingAllowed: false, petsAllowed: true, accessible: true, floor: '2',
    roomCapacity: 1, bedType: 'single',
    amenities: ['Terraza', 'Piscina'],
    acceptedTenantTypes: ['man', 'woman'],
    tenantRequirements: ['single-man', 'single-woman'],
  })
  expect(body).not.toHaveProperty('tenantRequirement')
})

test('explicit multiple room types override stale single type to prevent API 422', () => {
  const body = buildListingSearchBody({
    rentalMode: 'long', query: 'España', filters: { ...defaultFilters, roomType: 'Estudio' },
    roomTypes: ['Habitación individual', 'Habitación compartida'],
    minPrice: defaultFilters.minPrice, maxPrice: defaultFilters.maxPrice,
  })
  expect(body).toHaveProperty('roomTypes', ['Habitación individual', 'Habitación compartida'])
  expect(body).not.toHaveProperty('roomType')
})

test.describe('locale-specific mobile results render identical listing sets for the same region', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const route of [
    '/#/buscar?q=España&alquiler=long',
    '/#/buscar?q=Canarias&comunidad=05&alquiler=long',
  ]) {
    test(`identical ids, count and badges in all languages for ${route}`, async ({ browser }) => {
      const snapshots: Array<{ ids: string[]; count: string; badgeCounts: number[] }> = []
      for (const language of ['es', 'ru', 'en'] as const) {
        const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
        await context.addInitScript((locale) => {
          localStorage.setItem('112233:mobile-onboarding:v1', 'done')
          localStorage.setItem('112233:language:v1', locale)
        }, language)
        const page = await context.newPage()
        await page.goto(route)
        const results = page.getByTestId('mobile-results')
        await expect(results).toBeVisible()
        const cards = results.locator('.m2-result-card')
        await expect(cards.first()).toBeVisible()
        const ids = await cards.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-listing-id') ?? ''))
        const count = (await results.locator('.m2-results__header strong').textContent())?.match(/\d+/)?.[0] ?? ''
        const badgeCounts = await cards.locator('.m2-result-card__badges').evaluateAll((nodes) => nodes.map((node) => node.querySelectorAll('span').length))
        snapshots.push({ ids, count, badgeCounts })
        await context.close()
      }
      expect(snapshots[1]).toEqual(snapshots[0])
      expect(snapshots[2]).toEqual(snapshots[0])
    })
  }
})

test('Clear removes hidden filters but keeps chosen community and rental mode', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.goto('/#/buscar?q=Canarias&comunidad=05&alquiler=long&precioMax=450&requisito=single-man&mascotas=No&servicios=Terraza&publicado=7d&ducha=Ducha%20privada')
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await results.getByRole('button', { name: 'Filtros' }).click()
  await results.getByRole('button', { name: 'Limpiar' }).click()
  await results.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect.poll(() => new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('precioMax')).toBeNull()
  const params = new URLSearchParams(new URL(page.url()).hash.split('?')[1])
  for (const key of ['requisito', 'mascotas', 'servicios', 'publicado', 'ducha', 'precioMax']) {
    expect(params.has(key), key).toBe(false)
  }
  expect(params.get('q')).toBe('Canarias')
  expect(params.get('comunidad')).toBe('05')
  expect(params.get('alquiler')).toBe('long')
})
