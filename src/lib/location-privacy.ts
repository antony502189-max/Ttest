import type { Coordinates } from '@/types'

const EARTH_RADIUS_METERS = 6_371_000

export function distanceMeters(left: Coordinates, right: Coordinates) {
  const lat1 = left.lat * Math.PI / 180
  const lat2 = right.lat * Math.PI / 180
  const deltaLat = (right.lat - left.lat) * Math.PI / 180
  const deltaLng = (right.lng - left.lng) * Math.PI / 180
  const a = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(a)))
}

/**
 * Public owner-created listings use the host-confirmed map coordinate.
 * Keep this compatibility helper while callers migrate away from the old
 * approximate-location contract; it must never move the point.
 */
export function approximatePublicCoordinates(exact: Coordinates): Coordinates {
  return { lat: exact.lat, lng: exact.lng }
}
