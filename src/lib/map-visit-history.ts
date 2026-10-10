/**
 * Local, device-scoped map history (no account, cookies or server writes).
 *
 * Explicit camera/deep-link parameters always take priority. The last map
 * viewport is only a fallback when a visitor opens a NEW map search.
 */
export type MapViewport = { lat: number; lng: number; zoom: number }

export const MAP_VISIT_KEY = '112233:map-last-viewport:v1'
export const FIRST_MAP_VIEWPORT: Readonly<MapViewport> = {
  // Atlantic midpoint: a first-time visitor sees the Canaries and mainland
  // Spain rather than a close-up of an arbitrary property.
  lat: 32.45, lng: -11.2, zoom: 5.25,
}
const MAX_AGE_MS = 180 * 24 * 60 * 60 * 1000

export function validMapViewport(value: unknown): value is MapViewport {
  if (!value || typeof value !== 'object') return false
  const camera = value as Partial<MapViewport>
  return typeof camera.lat === 'number' && Number.isFinite(camera.lat)
    && camera.lat >= -85 && camera.lat <= 85
    && typeof camera.lng === 'number' && Number.isFinite(camera.lng)
    && camera.lng >= -180 && camera.lng <= 180
    && typeof camera.zoom === 'number' && Number.isFinite(camera.zoom)
    && camera.zoom >= 2 && camera.zoom <= 19
}

export function mapViewportFromParams(params: URLSearchParams): MapViewport | null {
  if (!['mapLat', 'mapLng', 'mapZoom'].every((key) => params.has(key))) return null
  const camera = {
    lat: Number(params.get('mapLat')),
    lng: Number(params.get('mapLng')),
    zoom: Number(params.get('mapZoom')),
  }
  return validMapViewport(camera) ? camera : null
}

export function readLastMapViewport(): MapViewport | null {
  try {
    const raw = localStorage.getItem(MAP_VISIT_KEY)
    if (!raw) return null
    const record: unknown = JSON.parse(raw)
    if (!record || typeof record !== 'object') return null
    const { camera, savedAt } = record as { camera?: unknown; savedAt?: unknown }
    if (typeof savedAt !== 'number' || !Number.isFinite(savedAt)
      || savedAt > Date.now() + 60_000 || Date.now() - savedAt > MAX_AGE_MS
      || !validMapViewport(camera)) return null
    return { lat: camera.lat, lng: camera.lng, zoom: camera.zoom }
  } catch {
    // Browsers can refuse storage (incognito/quota/security restrictions).
    return null
  }
}

export function rememberMapViewport(camera: MapViewport): void {
  if (!validMapViewport(camera)) return
  try {
    const previous = readLastMapViewport()
    // Map's idle event fires repeatedly without movement; avoid needless I/O.
    if (previous
      && Math.abs(previous.lat - camera.lat) < 0.00001
      && Math.abs(previous.lng - camera.lng) < 0.00001
      && Math.abs(previous.zoom - camera.zoom) < 0.001) return
    localStorage.setItem(MAP_VISIT_KEY, JSON.stringify({
      camera: { lat: camera.lat, lng: camera.lng, zoom: camera.zoom },
      savedAt: Date.now(),
    }))
  } catch {
    // Navigation and map browsing must keep working when storage is denied.
  }
}
