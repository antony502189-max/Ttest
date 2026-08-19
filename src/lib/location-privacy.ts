import { TENERIFE_CENTER, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

const EARTH_RADIUS_METERS = 6_371_000
const PUBLIC_OFFSET_METERS = 220

function seedFor(point: Coordinates) {
  const source = `${point.lat.toFixed(6)},${point.lng.toFixed(6)}`
  let hash = 2166136261
  for (const character of source) {
    hash ^= character.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
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

function bearingTowards(origin: Coordinates, target: Coordinates) {
  const lat1 = origin.lat * Math.PI / 180
  const lat2 = target.lat * Math.PI / 180
  const deltaLng = (target.lng - origin.lng) * Math.PI / 180
  return Math.atan2(
    Math.sin(deltaLng) * Math.cos(lat2),
    Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng),
  )
}

export function distanceMeters(left: Coordinates, right: Coordinates) {
  const lat1 = left.lat * Math.PI / 180
  const lat2 = right.lat * Math.PI / 180
  const deltaLat = (right.lat - left.lat) * Math.PI / 180
  const deltaLng = (right.lng - left.lng) * Math.PI / 180
  const a = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(a)))
}

export function approximatePublicCoordinates(exact: Coordinates): Coordinates {
  const seed = seedFor(exact)
  const initialAngle = (seed % 360) * Math.PI / 180
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const candidate = offsetPoint(exact, PUBLIC_OFFSET_METERS, initialAngle + attempt * Math.PI / 4)
    if (isInsideTenerife(candidate)) return candidate
  }
  return offsetPoint(exact, PUBLIC_OFFSET_METERS, bearingTowards(exact, TENERIFE_CENTER))
}
