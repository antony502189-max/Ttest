import type { Coordinates } from '@/types'
import { communityAtCoordinates } from '@/lib/spain-communities'

export type GeolocationFailure = 'unsupported' | 'denied' | 'unavailable' | 'timeout' | 'outside'
export type GeolocationResult =
  | { ok: true; coordinates: Coordinates }
  | { ok: false; reason: GeolocationFailure }

const TENERIFE_BOUNDS = {
  north: 28.62,
  south: 27.95,
  east: -16.08,
  west: -16.96,
}

export function isInsideSpain({ lat, lng }: Coordinates) {
  return Boolean(communityAtCoordinates(lat, lng))
    || (lat >= 35.85 && lat <= 35.93 && lng >= -5.4 && lng <= -5.27)
    || (lat >= 35.26 && lat <= 35.33 && lng >= -2.99 && lng <= -2.91)
}

const FALLBACK_OPTIONS: PositionOptions = {
  enableHighAccuracy: false,
  timeout: 15_000,
  maximumAge: 300_000,
}

export function isInsideTenerife({ lat, lng }: Coordinates) {
  return lat >= TENERIFE_BOUNDS.south
    && lat <= TENERIFE_BOUNDS.north
    && lng >= TENERIFE_BOUNDS.west
    && lng <= TENERIFE_BOUNDS.east
}

function failureReason(error: GeolocationPositionError): GeolocationFailure {
  if (error.code === error.PERMISSION_DENIED) return 'denied'
  if (error.code === error.TIMEOUT) return 'timeout'
  return 'unavailable'
}

export function requestCurrentLocation(options: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 10_000,
  maximumAge: 60_000,
}): Promise<GeolocationResult> {
  if (!navigator.geolocation) return Promise.resolve({ ok: false, reason: 'unsupported' })

  return new Promise((resolve) => {
    const resolvePosition = ({ coords }: GeolocationPosition) => {
      const coordinates = { lat: coords.latitude, lng: coords.longitude }
      // All mainland, Balearic and Canary autonomous communities are supported.
      // The old Tenerife-only bounds must not reject Madrid, Barcelona, etc.
      resolve(communityAtCoordinates(coordinates.lat, coordinates.lng)
        ? { ok: true, coordinates }
        : { ok: false, reason: 'outside' })
    }

    const resolveFailure = (error: GeolocationPositionError) => resolve({ ok: false, reason: failureReason(error) })

    navigator.geolocation.getCurrentPosition(
      resolvePosition,
      (error) => {
        const mayRetry = options.enableHighAccuracy !== false
          && (error.code === error.TIMEOUT || error.code === error.POSITION_UNAVAILABLE)

        if (!mayRetry) {
          resolveFailure(error)
          return
        }

        navigator.geolocation.getCurrentPosition(resolvePosition, resolveFailure, FALLBACK_OPTIONS)
      },
      options,
    )
  })
}

export function distanceKm(left: Coordinates, right: Coordinates) {
  const radians = (degrees: number) => degrees * Math.PI / 180
  const earthRadiusKm = 6371
  const latDelta = radians(right.lat - left.lat)
  const lngDelta = radians(right.lng - left.lng)
  const a = Math.sin(latDelta / 2) ** 2
    + Math.cos(radians(left.lat)) * Math.cos(radians(right.lat)) * Math.sin(lngDelta / 2) ** 2
  return earthRadiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}
