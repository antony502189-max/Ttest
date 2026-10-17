import { resolveProvince } from '@/lib/spain-provinces'
import type { ListingSearchInput } from '@/api/listings'

// The URL represents an explicitly applied map search, not merely the last
// camera position remembered for the next visit.
type SearchGeography = Pick<ListingSearchInput,
  'query' | 'autonomousCommunity' | 'provinceCode' | 'bounds' | 'polygon' | 'center' | 'radiusKm'
>

function validCoordinate(value: string, limit: number): number | null {
  if (!value.trim()) return null
  const number = Number(value)
  return Number.isFinite(number) && Math.abs(number) <= limit ? number : null
}

function selectedPolygon(params: URLSearchParams): NonNullable<SearchGeography['polygon']> | null {
  const raw = params.get('poligono')
  if (!raw) return null
  const points = raw.split(';').flatMap((pair) => {
    const parts = pair.split(',')
    if (parts.length !== 2) return []
    const latitude = validCoordinate(parts[0], 90)
    const longitude = validCoordinate(parts[1], 180)
    return latitude === null || longitude === null ? [] : [{ latitude, longitude }]
  })
  if (new Set(points.map((point) => `${point.latitude},${point.longitude}`)).size < 3) return null
  // The listing search API accepts at most 100 vertices including a closing
  // point. Sample large freehand drawings rather than dropping the area filter.
  if (points.length > 99) {
    return Array.from({ length: 99 }, (_, index) => points[Math.floor(index * points.length / 99)])
  }
  return points
}

function selectedBounds(params: URLSearchParams): NonNullable<SearchGeography['bounds']> | null {
  const keys = ['norte', 'sur', 'este', 'oeste'] as const
  if (!keys.every((key) => params.has(key))) return null
  const values = keys.map((key, index) => validCoordinate(params.get(key) ?? '', index < 2 ? 90 : 180))
  if (values.some((value) => value === null)) return null
  const [north, south, east, west] = values as number[]
  return north > south && east > west ? { north, south, east, west } : null
}

export function searchGeographyFromParams(params: URLSearchParams): SearchGeography {
  const polygon = selectedPolygon(params)
  if (polygon) return { query: 'España', polygon }

  const bounds = selectedBounds(params)
  if (bounds) return { query: 'España', bounds }

  const latitude = params.has('lat') ? validCoordinate(params.get('lat') ?? '', 90) : null
  const longitude = params.has('lng') ? validCoordinate(params.get('lng') ?? '', 180) : null
  if (params.get('cerca') === '1' && latitude !== null && longitude !== null) {
    return {
      query: 'España',
      center: { latitude, longitude },
      radiusKm: Math.min(50, Math.max(1, Number(params.get('radio')) || 15)),
    }
  }

  return {
    query: params.get('q')?.trim() || 'España',
    provinceCode: params.get('provincia') || (!params.has('comunidad') ? resolveProvince(params.get('q') ?? '')?.id : undefined),
    autonomousCommunity: params.get('comunidad') || undefined,
  }
}
