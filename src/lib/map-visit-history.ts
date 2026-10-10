/**
 * Device-local memory of the last area the visitor explored on the results map.
 * We store only its geographic center, not the previous zoom: on each new
 * search a 300 km radius must fit the CURRENT screen (desktop or mobile).
 *
 * A fresh visitor has no record. Camera bookmarks and named-area searches
 * take precedence over this fallback.
 */
export type MapViewport = { lat: number; lng: number; zoom: number }
export type MapCenter = Pick<MapViewport, 'lat' | 'lng'>

export const MAP_VISIT_KEY = '112233:map-last-search-area:v2'
export const MAP_RECALL_RADIUS_KM = 300
export const FIRST_MAP_VIEWPORT: Readonly<MapViewport> = {
  // First-time Atlantic overview including both Tenerife and mainland Spain.
  lat: 32.45, lng: -11.2, zoom: 5.25,
}
const MAX_AGE_MS = 180 * 24 * 60 * 60 * 1000
const EARTH_RADIUS_KM = 6371.0088
const MAX_MERCATOR_LAT = 85.05112878

function validMapCenter(value: unknown): value is MapCenter {
  if (!value || typeof value !== 'object') return false
  const center = value as Partial<MapCenter>
  return typeof center.lat === 'number' && Number.isFinite(center.lat)
    && center.lat >= -85 && center.lat <= 85
    && typeof center.lng === 'number' && Number.isFinite(center.lng)
    && center.lng >= -180 && center.lng <= 180
}

export function validMapViewport(value: unknown): value is MapViewport {
  if (!validMapCenter(value)) return false
  const { zoom } = value as MapViewport
  return typeof zoom === 'number' && Number.isFinite(zoom) && zoom >= 2 && zoom <= 19
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

export function readLastMapCenter(): MapCenter | null {
  try {
    const raw = localStorage.getItem(MAP_VISIT_KEY)
    if (!raw) return null
    const record: unknown = JSON.parse(raw)
    if (!record || typeof record !== 'object') return null
    const { center, savedAt } = record as { center?: unknown; savedAt?: unknown }
    if (typeof savedAt !== 'number' || !Number.isFinite(savedAt)
      || savedAt > Date.now() + 60_000 || Date.now() - savedAt > MAX_AGE_MS
      || !validMapCenter(center)) return null
    return { lat: center.lat, lng: center.lng }
  } catch {
    // Restricted storage must not prevent a search.
    return null
  }
}

function mercatorY(latitude: number): number {
  const phi = Math.max(-MAX_MERCATOR_LAT, Math.min(MAX_MERCATOR_LAT, latitude)) * Math.PI / 180
  return (1 - Math.log(Math.tan(Math.PI / 4 + phi / 2)) / Math.PI) / 2
}

/** Fit the exact 300 km geographic radius inside the map canvas, with no artificial zoom-out margin. */
export function viewportForRememberedArea(center: MapCenter, width: number, height: number): MapViewport {
  const angularRadius = MAP_RECALL_RADIUS_KM / EARTH_RADIUS_KM
  const latitudeRadius = angularRadius * 180 / Math.PI
  const phi = center.lat * Math.PI / 180
  const longitudeRadius = Math.abs(Math.cos(phi)) <= Math.sin(angularRadius)
    ? 180 : Math.asin(Math.min(1, Math.sin(angularRadius) / Math.cos(phi))) * 180 / Math.PI
  const longitudeFraction = Math.min(1, 2 * longitudeRadius / 360)
  const latitudeFraction = Math.abs(mercatorY(center.lat - latitudeRadius) - mercatorY(center.lat + latitudeRadius))

  // Match the 600 km diameter to the canvas' limiting dimension exactly.
  // Do not shrink the screen by 20%, or round down to quarter zoom levels:
  // both cause the map to reopen noticeably farther out than requested.
  const mapWidth = Math.max(1, width > 0 ? width : 390)
  const mapHeight = Math.max(1, height > 0 ? height : 600)
  const zoom = Math.min(
    Math.log2(mapWidth / (256 * longitudeFraction)),
    Math.log2(mapHeight / (256 * latitudeFraction)),
  )
  return { ...center, zoom: Math.max(2, Math.min(19, zoom)) }
}

export function readLastMapViewport(width = 390, height = 600): MapViewport | null {
  const center = readLastMapCenter()
  return center ? viewportForRememberedArea(center, width, height) : null
}

/**
 * Called only after a visitor actually explores or searches the map.
 * Initialization/automatic marker fitting MUST NOT write map history.
 */
export function rememberMapViewport(camera: MapViewport): void {
  if (!validMapViewport(camera)) return
  try {
    const previous = readLastMapCenter()
    if (previous
      && Math.abs(previous.lat - camera.lat) < 0.00001
      && Math.abs(previous.lng - camera.lng) < 0.00001) return
    localStorage.setItem(MAP_VISIT_KEY, JSON.stringify({
      center: { lat: camera.lat, lng: camera.lng },
      savedAt: Date.now(),
    }))
  } catch {
    // Private mode, blocked storage, or quota errors are non-fatal.
  }
}
