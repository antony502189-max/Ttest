import type { Coordinates, Listing } from '@/types'

const EARTH_RADIUS_METERS = 6_371_000
const RING_CAPACITY = 8
const RING_SPACING_METERS = 60

type MarkerListing = Pick<Listing, 'id' | 'coordinates'>

export type DisplayMarkerPosition = {
  position: Coordinates
  coincidentCount: number
}

function coordinateKey(point: Coordinates) {
  return `${point.lat.toFixed(7)},${point.lng.toFixed(7)}`
}

function offsetPoint(origin: Coordinates, distanceMeters: number, angleRadians: number): Coordinates {
  const angularDistance = distanceMeters / EARTH_RADIUS_METERS
  const lat1 = origin.lat * Math.PI / 180
  const lng1 = origin.lng * Math.PI / 180
  const sinLat1 = Math.sin(lat1)
  const cosLat1 = Math.cos(lat1)
  const sinDistance = Math.sin(angularDistance)
  const cosDistance = Math.cos(angularDistance)
  const lat2 = Math.asin(sinLat1 * cosDistance + cosLat1 * sinDistance * Math.cos(angleRadians))
  const lng2 = lng1 + Math.atan2(
    Math.sin(angleRadians) * sinDistance * cosLat1,
    cosDistance - sinLat1 * Math.sin(lat2),
  )
  return { lat: lat2 * 180 / Math.PI, lng: lng2 * 180 / Math.PI }
}

/**
 * MarkerClusterer stops clustering beyond its max zoom. If several listings
 * share the same public coordinate, their price markers would then sit exactly
 * on top of each other and Google would display only one of them. Spread only
 * truly coincident public points into deterministic rings for display. The
 * stored/public coordinates remain unchanged and are still used everywhere
 * outside the map marker presentation.
 */
export function buildDisplayMarkerPositions(items: MarkerListing[]) {
  const groups = new Map<string, MarkerListing[]>()
  for (const item of items) {
    const key = coordinateKey(item.coordinates)
    groups.set(key, [...(groups.get(key) ?? []), item])
  }

  const positions = new Map<string, DisplayMarkerPosition>()
  for (const group of groups.values()) {
    if (group.length === 1) {
      positions.set(group[0].id, { position: group[0].coordinates, coincidentCount: 1 })
      continue
    }

    const ordered = [...group].sort((left, right) => left.id.localeCompare(right.id))
    ordered.forEach((item, index) => {
      const ring = Math.floor(index / RING_CAPACITY)
      const ringStart = ring * RING_CAPACITY
      const ringCount = Math.min(RING_CAPACITY, ordered.length - ringStart)
      const indexInRing = index - ringStart
      const radius = RING_SPACING_METERS * (ring + 1)
      const phase = ring % 2 === 0 ? 0 : Math.PI / ringCount
      const angle = -Math.PI / 2 + phase + (2 * Math.PI * indexInRing / ringCount)
      positions.set(item.id, {
        position: offsetPoint(item.coordinates, radius, angle),
        coincidentCount: ordered.length,
      })
    })
  }
  return positions
}
