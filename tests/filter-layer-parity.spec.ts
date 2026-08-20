import { expect, test } from '@playwright/test'
import { defaultFilters, initialListings } from '@/data/listings'
import { filterListings } from '@/lib/search'
import type { Filters, Listing, RentalMode } from '@/types'

function longListing(): Listing {
  const seed = initialListings.find((item) => item.rentalMode === 'long')!
  return {
    ...seed,
    id: 'filter-parity-long',
    city: 'Santa Cruz de Tenerife',
    area: 'Santa Cruz de Tenerife',
    rentalMode: 'long',
    status: 'Publicado',
    price: 725,
    monthlyPrice: 725,
    nightlyPrice: undefined,
    roomType: 'Habitación individual',
    availableFrom: '2026-01-01',
    availableUntil: '2030-12-31',
    minimumStayMonths: 1,
    minimumNights: undefined,
    depositAmount: 0,
    billsIncluded: true,
    bathroom: 'Baño privado',
    kitchen: 'Cocina privada',
    furnished: true,
    roomSizeM2: 18,
    homeSizeM2: 90,
    bathroomCount: 2,
    rentalUnit: 'room',
    bedType: 'double',
    bedCount: 1,
    currentResidents: 5,
    roomCapacity: 2,
    currentRoomResidents: 1,
    availableSpots: 1,
    shower: 'Ducha privada',
    toilet: 'Aseo privado',
    tenantRequirement: 'single-man',
    smokingAllowed: true,
    petsAllowed: true,
    childrenAllowed: false,
    couplesAllowed: true,
    householdGender: 'mixed',
    householdHasChildren: false,
    heatingType: 'individual',
    accessible: true,
    floor: 'top',
    acceptedTenantTypes: ['man', 'woman'],
    empadronamientoAllowed: true,
    restrictions: ['No fumar', 'Gastos incluidos'],
    amenities: ['Wi-Fi', 'Aire acondicionado', 'Jardín'],
    advertiserType: 'Profesional',
    publishedAt: new Date().toISOString(),
    expiresAt: '2099-12-31',
  }
}

function holidayListing(minimumNights: number | undefined): Listing {
  const listing = longListing()
  return {
    ...listing,
    id: `filter-parity-holiday-${minimumNights ?? 'unknown'}`,
    rentalMode: 'holiday',
    cadence: 'noche',
    price: 80,
    monthlyPrice: undefined,
    nightlyPrice: 80,
    minimumStayMonths: 0,
    minimumNights,
  }
}

function filters(patch: Partial<Filters>): Filters {
  return {
    ...defaultFilters,
    areas: [],
    conditions: [],
    tenantRequirements: [],
    acceptedTenantTypes: [],
    amenities: [],
    ...patch,
  }
}

function matches(listing: Listing, mode: RentalMode, patch: Partial<Filters>) {
  return filterListings([listing], mode, filters(patch)).map((item) => item.id)
}

test('FILTER-LAYER local filter engine applies every public search filter with backend-compatible semantics', () => {
  const listing = longListing()
  const cases: Array<{ name: string; match: Partial<Filters>; miss: Partial<Filters> }> = [
    { name: 'price', match: { minPrice: 700, maxPrice: 800 }, miss: { minPrice: 726 } },
    { name: 'area', match: { areas: ['Santa Cruz de Tenerife'] }, miss: { areas: ['Adeje'] } },
    { name: 'room type', match: { roomType: 'Habitación individual' }, miss: { roomType: 'Estudio' } },
    { name: 'available date', match: { available: '2028-01-01' }, miss: { available: '2031-01-01' } },
    { name: 'available until', match: { availableUntil: '2030-01-01' }, miss: { availableUntil: '2031-01-01' } },
    { name: 'minimum stay', match: { minStay: '1' }, miss: { minStay: '0' } },
    { name: 'conditions', match: { conditions: ['No fumar'] }, miss: { conditions: ['Mascotas permitidas'] } },
    { name: 'tenant requirement', match: { tenantRequirement: 'single-man' }, miss: { tenantRequirement: 'couple' } },
    { name: 'bathroom', match: { bathroom: 'Baño privado' }, miss: { bathroom: 'Baño compartido' } },
    { name: 'kitchen', match: { kitchen: 'Cocina privada' }, miss: { kitchen: 'Cocina compartida' } },
    { name: 'furnished', match: { furnished: true }, miss: { furnished: true } },
    { name: 'bills included', match: { billsIncluded: true }, miss: { billsIncluded: true } },
    { name: 'deposit', match: { deposit: 'Sin fianza' }, miss: { deposit: 'Más de 1 mes' } },
    { name: 'room size', match: { roomSizeMin: 18, roomSizeMax: 18 }, miss: { roomSizeMin: 19 } },
    { name: 'home size', match: { homeSizeMin: 90, homeSizeMax: 90 }, miss: { homeSizeMin: 91 } },
    { name: 'bathroom count', match: { bathroomCountMin: 2 }, miss: { bathroomCountMin: 3 } },
    { name: 'rental unit', match: { rentalUnit: 'room' }, miss: { rentalUnit: 'bed' } },
    { name: 'bed type', match: { bedType: 'double' }, miss: { bedType: 'single' } },
    { name: 'bed count', match: { bedCountMin: 1 }, miss: { bedCountMin: 2 } },
    { name: 'shower', match: { shower: 'Ducha privada' }, miss: { shower: 'Ducha compartida' } },
    { name: 'toilet', match: { toilet: 'Aseo privado' }, miss: { toilet: 'Aseo compartido' } },
    { name: 'current residents', match: { currentResidents: '5+' }, miss: { currentResidents: '4' } },
    { name: 'room residents', match: { roomResidents: '1' }, miss: { roomResidents: '0' } },
    { name: 'room capacity', match: { roomCapacity: '2' }, miss: { roomCapacity: '1' } },
    { name: 'available spots', match: { availableSpotsMin: 1 }, miss: { availableSpotsMin: 2 } },
    { name: 'smoking', match: { smoking: 'Sí' }, miss: { smoking: 'No' } },
    { name: 'pets', match: { pets: 'Sí' }, miss: { pets: 'No' } },
    { name: 'children', match: { children: 'No' }, miss: { children: 'Sí' } },
    { name: 'couples', match: { couplesAllowed: 'Sí' }, miss: { couplesAllowed: 'No' } },
    { name: 'household gender', match: { householdGender: 'mixed' }, miss: { householdGender: 'women' } },
    { name: 'household children', match: { householdHasChildren: 'No' }, miss: { householdHasChildren: 'Sí' } },
    { name: 'heating', match: { heatingType: 'individual' }, miss: { heatingType: 'central' } },
    { name: 'accessible', match: { accessible: 'Sí' }, miss: { accessible: 'No' } },
    { name: 'floor', match: { floor: 'top' }, miss: { floor: '1' } },
    { name: 'accepted tenant', match: { acceptedTenantTypes: ['woman'] }, miss: { acceptedTenantTypes: ['family'] } },
    { name: 'registration', match: { empadronamiento: 'Sí' }, miss: { empadronamiento: 'No' } },
    { name: 'publication age', match: { publicationDate: '24h' }, miss: { publicationDate: '24h' } },
    { name: 'advertiser', match: { advertiserType: 'Profesional' }, miss: { advertiserType: 'Particular' } },
    { name: 'amenities', match: { amenities: ['Aire acondicionado', 'Jardín'] }, miss: { amenities: ['Piscina'] } },
  ]

  for (const item of cases) {
    expect(matches(listing, 'long', item.match), `${item.name} should include matching listing`).toEqual([listing.id])
    if (item.name === 'furnished') {
      expect(matches({ ...listing, furnished: false }, 'long', item.miss), `${item.name} should exclude false listing`).toEqual([])
    } else if (item.name === 'bills included') {
      expect(matches({ ...listing, billsIncluded: false }, 'long', item.miss), `${item.name} should exclude false listing`).toEqual([])
    } else if (item.name === 'publication age') {
      expect(matches({ ...listing, publishedAt: '2020-01-01T00:00:00Z' }, 'long', item.miss), `${item.name} should exclude old listing`).toEqual([])
    } else {
      expect(matches(listing, 'long', item.miss), `${item.name} should exclude non-matching listing`).toEqual([])
    }
  }
})

test('FILTER-LAYER holiday minimum-night filter treats unknown minimum as non-match like backend SQL', () => {
  expect(matches(holidayListing(3), 'holiday', { minimumNights: 3 })).toEqual(['filter-parity-holiday-3'])
  expect(matches(holidayListing(4), 'holiday', { minimumNights: 3 })).toEqual([])
  expect(matches(holidayListing(undefined), 'holiday', { minimumNights: 3 })).toEqual([])
})

test('FILTER-LAYER open-ended move-out date remains a match', () => {
  const listing = { ...longListing(), availableUntil: undefined }
  expect(matches(listing, 'long', { availableUntil: '2035-01-01' })).toEqual([listing.id])
})
