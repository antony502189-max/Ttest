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
  const capacities = (params.get('capacidades') ?? '').split('|').filter(Boolean).map(Number).filter(Number.isFinite)

  const filtered = filterListings(
    listings.filter((listing) => !discarded.has(listing.id)),
    rentalMode,
    filters,
  ).filter((listing) => {
    if (!location || !listingMatchesTenerifeLocation(listing, location)) return false
    if (roomTypes.length && !roomTypes.includes(listing.roomType)) return false
    if (capacities.length && !capacities.includes(listing.roomCapacity)) return false
    if (polygonApplied && polygon.length >= 3 && !pointInPolygon(listing.coordinates, polygon)) return false
    if (nearbyCenter && distanceKm(listing.coordinates, nearbyCenter) > radiusKm) return false
    return true
  })

  return sortListings(filtered, filters.sort)
}
