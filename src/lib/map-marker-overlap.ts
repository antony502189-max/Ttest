import type { MappedListing } from '@/types'

type MarkerListing = Pick<MappedListing, 'id' | 'coordinates'>

export type DisplayMarkerPosition = {
  position: MarkerListing['coordinates']
  coincidentCount: number
}

function coordinateKey(point: MarkerListing['coordinates']) {
  return `${point.lat.toFixed(7)},${point.lng.toFixed(7)}`
}

/**
 * Never alter geographic coordinates to solve visual overlap. Listings that
 * share one dwelling stay on the same real point and MarkerClusterer renders
 * them as a count cluster, including at the map's maximum user zoom.
 */
export function exactCoincidentListingIds(items: MarkerListing[], candidateIds: string[]) {
  if (candidateIds.length < 2) return []
  const byId = new Map(items.map((item) => [item.id, item]))
  const candidates = candidateIds.flatMap((id) => {
    const item = byId.get(id)
    return item ? [item] : []
  })
  if (candidates.length !== candidateIds.length || candidates.length < 2) return []
  const key = coordinateKey(candidates[0].coordinates)
  return candidates.every((item) => coordinateKey(item.coordinates) === key)
    ? candidates.map((item) => item.id)
    : []
}

export function coincidentListingIdsFor(items: MarkerListing[], listingId: string) {
  const selected = items.find((item) => item.id === listingId)
  if (!selected) return []
  const key = coordinateKey(selected.coordinates)
  return items.filter((item) => coordinateKey(item.coordinates) === key).map((item) => item.id)
}

export function buildDisplayMarkerPositions(items: MarkerListing[]) {
  const counts = new Map<string, number>()
  for (const item of items) {
    const key = coordinateKey(item.coordinates)
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }

  return new Map(items.map((item) => [
    item.id,
    {
      position: item.coordinates,
      coincidentCount: counts.get(coordinateKey(item.coordinates)) ?? 1,
    },
  ]))
}
