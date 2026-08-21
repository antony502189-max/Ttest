import { defaultFilters } from '@/data/listings'
import { distanceKm } from '@/lib/geolocation'
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
  const roomSizeFilterActive = filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax

  // Imported listings may legitimately omit roomSizeM2. The default size
  // controls represent an inactive filter, so unknown metadata must survive
  // until the user explicitly narrows the size range.
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
    if (polygonApplied && polygon.length >= 3 && !pointInPolygon(listing.coordinates, polygon)) return false
    if (nearbyCenter && distanceKm(listing.coordinates, nearbyCenter) > radiusKm) return false
    return true
  }).map((listing) => originalById.get(listing.id) ?? listing)

  return sortListings(filtered, filters.sort)
}
