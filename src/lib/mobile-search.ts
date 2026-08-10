import { defaultFilters } from '@/data/listings'
import { distanceKm } from '@/lib/geolocation'
import { getBedroomCount } from '@/lib/listings'
import { filterListings, pointInPolygon, sortListings } from '@/lib/search'
import { listingMatchesTenerifeLocation, resolveTenerifeLocation } from '@/lib/tenerife'
import type { Filters, Listing, MapPolygonPoint, RentalMode } from '@/types'

type MobileSearchInput = {
  listings: Listing[]
  discarded: Set<string>
  rentalMode: RentalMode
  filters: Filters
  polygon: MapPolygonPoint[]
  query: string
  params: URLSearchParams
}

export function selectMobileSearchListings({
  listings,
  discarded,
  rentalMode,
  filters,
  polygon,
  query,
  params,
}: MobileSearchInput) {
  const location = resolveTenerifeLocation(query || 'Tenerife')
  const nearby = params.get('cerca') === '1'
  const polygonApplied = params.get('dibujar') !== '1'
  const lat = Number(params.get('lat'))
  const lng = Number(params.get('lng'))
  const radiusKm = Math.min(50, Math.max(1, Number(params.get('radio')) || 15))
  const nearbyCenter = nearby && Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null
  const roomTypes = (params.get('tiposHabitacion') ?? '').split('|').filter(Boolean)
  const bedroomFilters = (params.get('habitaciones') ?? '').split('|').filter(Boolean)
  const exactBedroomCounts = bedroomFilters.map(Number).filter((value) => Number.isInteger(value) && value >= 1 && value <= 10)
  const moreThanTenBedrooms = bedroomFilters.includes('10+')
  const roomSizeFilterActive = filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax

  // `filterListings` intentionally rejects unknown room sizes when a size
  // constraint is active. Imported listings are allowed to omit roomSizeM2,
  // so the default 0..50 UI range must not silently become a constraint.
  // Use a temporary comparable value only for filtering and restore the
  // original listing objects before returning results.
  const originalById = new Map(listings.map((listing) => [listing.id, listing]))
  const comparableListings = roomSizeFilterActive
    ? listings
    : listings.map((listing) => listing.roomSizeM2 == null ? { ...listing, roomSizeM2: defaultFilters.roomSizeMin } : listing)

  const filtered = filterListings(
    comparableListings.filter((listing) => !discarded.has(listing.id)),
    rentalMode,
    filters,
  ).filter((listing) => {
    if (!location || !listingMatchesTenerifeLocation(listing, location)) return false
    if (roomTypes.length && !roomTypes.includes(listing.roomType)) return false
    const bedroomCount = getBedroomCount(listing)
    if (bedroomFilters.length && !exactBedroomCounts.includes(bedroomCount) && !(moreThanTenBedrooms && bedroomCount > 10)) return false
    if (polygonApplied && polygon.length >= 3 && !pointInPolygon(listing.coordinates, polygon)) return false
    if (nearbyCenter && distanceKm(listing.coordinates, nearbyCenter) > radiusKm) return false
    return true
  }).map((listing) => originalById.get(listing.id) ?? listing)

  return sortListings(filtered, filters.sort)
}
