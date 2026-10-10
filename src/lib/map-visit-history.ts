/**
 * Device-local memory of the last area the visitor explored on the results map.
 * We store only the last explored geographic point, not the previous zoom.
 * On a new visit it resolves to a deterministic zone with a 70 km radius,
 * fitted to the current map canvas. Existing v2 records remain readable.
 *
 * A fresh visitor has no record. Camera bookmarks and named-area searches
 * take precedence over this fallback.
 */
export type MapViewport = { lat: number; lng: number; zoom: number }
export type MapCenter = Pick<MapViewport, 'lat' | 'lng'>

export const MAP_VISIT_KEY = '112233:map-last-search-area:v2'
export const MAP_RECALL_RADIUS_KM = 70
export const FIRST_MAP_VIEWPORT: Readonly<MapViewport> = {
  // First-time Atlantic overview including both Tenerife and mainland Spain.
  lat: 32.45, lng: -11.2, zoom: 5.25,
}
const MAX_AGE_MS = 180 * 24 * 60 * 60 * 1000
const EARTH_RADIUS_KM = 6371.0088
const MAX_MERCATOR_LAT = 85.05112878
const KM_PER_DEGREE = EARTH_RADIUS_KM * Math.PI / 180

// Pointy-top hexagonal coverage: each hexagon's furthest vertex is 70 km
// from its center, so the corresponding circular search regions overlap
// without leaving gaps. The grid is virtual; no extra circles are rendered.
// Row-specific longitude spacing corrects for latitude around Spain.
const ZONE_ORIGIN: MapCenter = { lat: 33, lng: -10 }
const ZONE_ROW_KM = 1.5 * MAP_RECALL_RADIUS_KM
const ZONE_COLUMN_KM = Math.sqrt(3) * MAP_RECALL_RADIUS_KM

function normalizeLongitude(longitude: number): number {
  return ((longitude + 180) % 360 + 360) % 360 - 180
}

function geographicDistanceKm(first: MapCenter, second: MapCenter): number {
  const firstLat = first.lat * Math.PI / 180
  const secondLat = second.lat * Math.PI / 180
  const dLat = secondLat - firstLat
  const dLng = normalizeLongitude(second.lng - first.lng) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(firstLat) * Math.cos(secondLat) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(Math.max(0, a))))
}

/**
 * Snap an explored point to the closest 70 km zone center.
 * Adjacent circles overlap, but the nearest-center rule gives every point
 * exactly one stable zone, without drawing boundaries over the listing map.
 */
export function mapZoneForCenter(point: MapCenter): MapCenter {
  if (!validMapCenter(point)) return point
  const nearestRow = Math.round((point.lat - ZONE_ORIGIN.lat) * KM_PER_DEGREE / ZONE_ROW_KM)
  const relativeLongitude = normalizeLongitude(point.lng - ZONE_ORIGIN.lng)
  let bestCenter: MapCenter = point
  let bestDistance = Infinity

  // Latitude rows have staggered column origins; checking neighboring rows
  // prevents a point near the border from being assigned to a farther zone.
  for (let row = nearestRow - 2; row <= nearestRow + 2; row++) {
    const rowLatitude = ZONE_ORIGIN.lat + row * ZONE_ROW_KM / KM_PER_DEGREE
    if (Math.abs(rowLatitude) > 85) continue
    const longitudeStep = ZONE_COLUMN_KM / (KM_PER_DEGREE * Math.cos(rowLatitude * Math.PI / 180))
    const offset = row % 2 === 0 ? 0 : 0.5
    const nearestColumn = Math.round(relativeLongitude / longitudeStep - offset)
    for (let column = nearestColumn - 1; column <= nearestColumn + 1; column++) {
      const candidate = {
        lat: rowLatitude,
        lng: normalizeLongitude(ZONE_ORIGIN.lng + (column + offset) * longitudeStep),
      }
      const distance = geographicDistanceKm(point, candidate)
      if (distance < bestDistance) {
        bestDistance = distance
        bestCenter = candidate
      }
    }
  }
  return bestCenter
}

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
    // Transparent migration of the previous exact-coordinate v2 history:
    // retain its timestamp and point, but display the nearest 70 km zone.
    return mapZoneForCenter(center)
  } catch {
    // Restricted storage must not prevent a search.
    return null
  }
}

function mercatorY(latitude: number): number {
  const phi = Math.max(-MAX_MERCATOR_LAT, Math.min(MAX_MERCATOR_LAT, latitude)) * Math.PI / 180
  return (1 - Math.log(Math.tan(Math.PI / 4 + phi / 2)) / Math.PI) / 2
}

/** Fit the selected 70 km zone's enclosing circle without extra zoom-out. */
export function viewportForRememberedArea(center: MapCenter, width: number, height: number): MapViewport {
  const angularRadius = MAP_RECALL_RADIUS_KM / EARTH_RADIUS_KM
  const latitudeRadius = angularRadius * 180 / Math.PI
  const phi = center.lat * Math.PI / 180
  const longitudeRadius = Math.abs(Math.cos(phi)) <= Math.sin(angularRadius)
    ? 180 : Math.asin(Math.min(1, Math.sin(angularRadius) / Math.cos(phi))) * 180 / Math.PI
  const longitudeFraction = Math.min(1, 2 * longitudeRadius / 360)
  const latitudeFraction = Math.abs(mercatorY(center.lat - latitudeRadius) - mercatorY(center.lat + latitudeRadius))

  // Match the 140 km diameter to the canvas' limiting dimension exactly,
  // without shrinking the viewport or rounding down fractional zoom.
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
    const previousZone = readLastMapCenter()
    const newZone = mapZoneForCenter(camera)
    // Small pans within one virtual zone should not trigger different regions
    // on the next visit or create unnecessary localStorage writes.
    if (previousZone
      && geographicDistanceKm(previousZone, newZone) < 0.001) return
    localStorage.setItem(MAP_VISIT_KEY, JSON.stringify({
      center: { lat: camera.lat, lng: camera.lng },
      savedAt: Date.now(),
    }))
  } catch {
    // Private mode, blocked storage, or quota errors are non-fatal.
  }
}
