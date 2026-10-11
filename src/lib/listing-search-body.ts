import { defaultFilters } from '@/data/listings'
import type { ListingSearchInput } from '@/api/listings'

export function buildListingSearchBody(input: ListingSearchInput): Record<string, unknown> {
  const { bounds, polygon, filters, minPrice, maxPrice, ...payload } = input
  const yesNo = (value: string) => value === 'Cualquiera' ? undefined : value === 'Sí'
  const publicationDays = filters.publicationDate === '24h' ? 1 : filters.publicationDate === '7d' ? 7 : filters.publicationDate === '30d' ? 30 : undefined
  const body = {
    ...payload,
    ...(minPrice !== defaultFilters.minPrice ? { minPrice } : {}),
    ...(maxPrice !== defaultFilters.maxPrice ? { maxPrice } : {}),
    query: input.query ?? 'Tenerife',
    roomTypes: input.roomTypes ?? [],
    center: input.center,
    radiusKm: input.radiusKm,
    ...(filters.roomType !== 'Cualquiera' && !input.roomTypes?.length ? { roomType: filters.roomType } : {}),
    ...(filters.available ? { availableFrom: filters.available } : {}),
    ...(filters.availableUntil ? { availableUntil: filters.availableUntil } : {}),
    ...(filters.minStay !== 'Cualquiera' ? { maxMinimumStayMonths: Number(filters.minStay) } : {}),
    ...(filters.conditions.length ? { restrictions: filters.conditions } : {}),
    ...(filters.tenantRequirement !== 'Cualquiera' && filters.tenantRequirement !== 'any'
      ? { tenantRequirement: filters.tenantRequirement }
      : {}),
    ...(filters.tenantRequirement === 'Cualquiera' && filters.tenantRequirements.length
      ? { tenantRequirements: filters.tenantRequirements }
      : {}),
    ...(filters.bathroom !== 'Cualquiera' ? { bathroom: filters.bathroom } : {}),
    ...(filters.kitchen !== 'Cualquiera' ? { kitchen: filters.kitchen } : {}),
    ...(filters.furnished ? { furnished: true } : {}),
    ...(filters.billsIncluded ? { billsIncluded: true } : {}),
    ...(filters.deposit !== 'Cualquiera' ? { deposit: filters.deposit } : {}),
    ...(filters.roomSizeMin !== defaultFilters.roomSizeMin ? { minRoomSizeM2: filters.roomSizeMin } : {}),
    ...(filters.roomSizeMax !== defaultFilters.roomSizeMax ? { maxRoomSizeM2: filters.roomSizeMax } : {}),
    ...(filters.homeSizeMin !== defaultFilters.homeSizeMin ? { minHomeSizeM2: filters.homeSizeMin } : {}),
    ...(filters.homeSizeMax !== defaultFilters.homeSizeMax ? { maxHomeSizeM2: filters.homeSizeMax } : {}),
    ...(filters.bathroomCountMin > 0 ? { minBathroomCount: filters.bathroomCountMin } : {}),
    ...(filters.rentalUnit !== 'Cualquiera' ? { rentalUnit: filters.rentalUnit } : {}),
    ...(filters.bedType !== 'Cualquiera' ? { bedType: filters.bedType } : {}),
    ...(filters.bedCountMin > 0 ? { minBedCount: filters.bedCountMin } : {}),
    ...(filters.shower !== 'Cualquiera' ? { shower: filters.shower } : {}),
    ...(filters.toilet !== 'Cualquiera' ? { toilet: filters.toilet } : {}),
    ...(filters.currentResidents === '5+' ? { minCurrentResidents: 5 } : filters.currentResidents !== 'Cualquiera' ? { currentResidents: Number(filters.currentResidents) } : {}),
    ...(filters.roomResidents !== 'Cualquiera' ? { currentRoomResidents: Number(filters.roomResidents) } : {}),
    ...(filters.roomCapacity !== 'Cualquiera' ? { roomCapacity: Number(filters.roomCapacity) } : {}),
    ...(filters.availableSpotsMin > 0 ? { minAvailableSpots: filters.availableSpotsMin } : {}),
    ...(input.rentalMode === 'holiday' && filters.minimumNights > 0 ? { maxMinimumNights: filters.minimumNights } : {}),
    ...(yesNo(filters.smoking) !== undefined ? { smokingAllowed: yesNo(filters.smoking) } : {}),
    ...(yesNo(filters.pets) !== undefined ? { petsAllowed: yesNo(filters.pets) } : {}),
    ...(yesNo(filters.children) !== undefined ? { childrenAllowed: yesNo(filters.children) } : {}),
    ...(yesNo(filters.couplesAllowed) !== undefined ? { couplesAllowed: yesNo(filters.couplesAllowed) } : {}),
    ...(filters.householdGender !== 'Cualquiera' ? { householdGender: filters.householdGender } : {}),
    ...(yesNo(filters.householdHasChildren) !== undefined ? { householdHasChildren: yesNo(filters.householdHasChildren) } : {}),
    ...(filters.heatingType !== 'Cualquiera' ? { heatingType: filters.heatingType } : {}),
    ...(yesNo(filters.accessible) !== undefined ? { accessible: yesNo(filters.accessible) } : {}),
    ...(filters.floor !== 'Cualquiera' ? { floor: filters.floor } : {}),
    ...(filters.acceptedTenantTypes.length ? { acceptedTenantTypes: filters.acceptedTenantTypes } : {}),
    ...(yesNo(filters.empadronamiento) !== undefined ? { empadronamientoAllowed: yesNo(filters.empadronamiento) } : {}),
    ...(publicationDays ? { publishedWithinDays: publicationDays } : {}),
    ...(filters.advertiserType !== 'Cualquiera' ? { advertiserType: filters.advertiserType } : {}),
    ...(filters.amenities.length ? { amenities: filters.amenities } : {}),
    ...(bounds ? {
      minLatitude: bounds.south, maxLatitude: bounds.north,
      minLongitude: bounds.west, maxLongitude: bounds.east,
    } : {}),
    ...(polygon?.length ? { polygon } : {}),
  }
  return body
}

