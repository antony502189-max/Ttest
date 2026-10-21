import { defaultFilters } from '@/data/listings'
import { searchGeographyFromParams } from '@/lib/search-geography'
import { distanceKm } from '@/lib/geolocation'
import { filterListings, filtersFromParams, pointInPolygon, sortListings } from '@/lib/search'
import { hasListingCoordinates } from '@/lib/listings'
import { listingMatchesTenerifeLocation, resolveTenerifeLocation } from '@/lib/tenerife'
import { getCommunity, listingInCommunity } from '@/lib/spain-communities'
import { listingInProvince } from '@/lib/spain-provinces'
import { listingInMunicipality } from '@/lib/spain-locations'
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

function routeScopedMobileFilters(filters: Filters, params: URLSearchParams): Filters {
  // The URL is the durable source of truth for filters that are not currently
  // editable in the mobile panel. Previously stale app-context values could
  // remain active invisibly and reduce a perfectly normal mobile search to
  // zero results. Keep draft/visible controls from the caller, but rebuild all
  // hidden dimensions from the current route.
  const route = filtersFromParams(params)
  return {
    ...route,
    minPrice: filters.minPrice,
    maxPrice: filters.maxPrice,
    roomSizeMin: filters.roomSizeMin,
    roomSizeMax: filters.roomSizeMax,
    roomType: filters.roomType,
    available: filters.available,
    availableUntil: filters.availableUntil,
    shower: filters.shower,
    toilet: filters.toilet,
    kitchen: filters.kitchen,
    bedType: filters.bedType,
    smoking: filters.smoking,
    accessible: filters.accessible,
    floor: filters.floor,
    amenities: filters.amenities,
  }
}

export function selectMobileSearchListings({
  listings,
  discarded,
  rentalMode,
  filters,
  params,
}: MobileSearchInput) {
  const geography = searchGeographyFromParams(params)
  const location = resolveTenerifeLocation(geography.query || 'Tenerife')
  const community = geography.autonomousCommunity
  const region = getCommunity(community)
  const countrySearch = ['españa', 'espana', 'spain', 'es'].includes((geography.query ?? '').trim().toLowerCase())
  const polygonApplied = params.get('dibujar') !== '1'
  const polygon = polygonApplied
    ? (geography.polygon ?? []).map(({ latitude, longitude }) => ({ lat: latitude, lng: longitude }))
    : []
  const nearbyCenter = geography.center
    ? { lat: geography.center.latitude, lng: geography.center.longitude }
    : null
  const radiusKm = geography.radiusKm ?? 15
  const roomTypes = (params.get('tiposHabitacion') ?? '').split('|').filter(Boolean)
  const effectiveFilters = routeScopedMobileFilters(filters, params)
  const roomSizeFilterActive = effectiveFilters.roomSizeMin !== defaultFilters.roomSizeMin || effectiveFilters.roomSizeMax !== defaultFilters.roomSizeMax

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
    effectiveFilters,
  ).filter((listing) => {
    if (geography.provinceCode && !listingInProvince(listing, geography.provinceCode)) return false
    if (geography.municipalityCode && !listingInMunicipality(listing, geography.municipalityCode)) return false
    if (community && !region) return false
    if (region && !listingInCommunity(listing, region.id)) return false
    if (!geography.provinceCode && !region && !countrySearch && (!location || !listingMatchesTenerifeLocation(listing, location))) return false
    if (roomTypes.length && !roomTypes.includes(listing.roomType)) return false
    if (polygonApplied && polygon.length >= 3) {
      if (!hasListingCoordinates(listing) || !pointInPolygon(listing.coordinates, polygon)) return false
    }
    if (geography.bounds) {
      const { north, south, east, west } = geography.bounds
      if (!hasListingCoordinates(listing) || listing.coordinates.lat > north || listing.coordinates.lat < south ||
        listing.coordinates.lng > east || listing.coordinates.lng < west) return false
    }
    if (nearbyCenter) {
      if (!hasListingCoordinates(listing) || distanceKm(listing.coordinates, nearbyCenter) > radiusKm) return false
    }
    return true
  }).map((listing) => originalById.get(listing.id) ?? listing)

  return sortListings(filtered, effectiveFilters.sort)
}
