import { expect, test } from '@playwright/test'
import { translateText } from '@/contexts/i18n-context'
import { defaultFilters, initialListings } from '@/data/listings'
import { compareListingFloors } from '@/lib/floor'
import { approximatePublicCoordinates, distanceMeters } from '@/lib/location-privacy'
import { filterListings } from '@/lib/search'
import type { Listing } from '@/types'

test('CUSTOMER-SYNC exact publication coordinates stay private and public point is deterministic', () => {
  const exact = { lat: 28.0521, lng: -16.7177 }
  const first = approximatePublicCoordinates(exact)
  const second = approximatePublicCoordinates(exact)
  expect(first).toEqual(second)
  expect(first).not.toEqual(exact)
  expect(distanceMeters(exact, first)).toBeGreaterThanOrEqual(150)
  expect(distanceMeters(exact, first)).toBeLessThanOrEqual(300)
})

test('CUSTOMER-SYNC floor ordering uses structured floor instead of listing id', () => {
  const listings: Array<Pick<Listing, 'id' | 'floor'>> = [
    { id: 'aaa', floor: 'top' },
    { id: 'zzz', floor: 'basement' },
    { id: 'middle', floor: '2' },
    { id: 'legacy', floor: null },
  ]
  const ascending = [...listings].sort((left, right) => compareListingFloors(left, right, 'asc'))
  const descending = [...listings].sort((left, right) => compareListingFloors(left, right, 'desc'))
  expect(ascending.map((listing) => listing.floor)).toEqual(['basement', '2', 'top', null])
  expect(descending.map((listing) => listing.floor)).toEqual(['top', '2', 'basement', null])
})

test('CUSTOMER-SYNC open-ended availability satisfies an optional requested move-out date', () => {
  const seed = initialListings.find((listing) => listing.rentalMode === 'long')
  expect(seed).toBeTruthy()
  const listing: Listing = {
    ...seed!,
    rentalMode: 'long',
    status: 'Publicado',
    availableFrom: '2020-01-01',
    availableUntil: undefined,
    expiresAt: '2099-01-01',
  }
  const filters = { ...defaultFilters, availableUntil: '2030-01-01' }
  expect(filterListings([listing], 'long', filters).map((item) => item.id)).toEqual([listing.id])
})

test('CUSTOMER-SYNC new filter and publication labels are localized', () => {
  expect(translateText('Jardín', 'ru')).toBe('Сад')
  expect(translateText('Jardín', 'en')).toBe('Garden')
  expect(translateText('Limpieza incluida', 'ru')).toBe('Уборка включена')
  expect(translateText('Limpieza incluida', 'en')).toBe('Cleaning included')
  expect(translateText('Planta', 'ru')).toBe('Этаж')
  expect(translateText('Última planta', 'en')).toBe('Top floor')
  expect(translateText('Calle y número', 'ru')).toBe('Улица и номер')
})
