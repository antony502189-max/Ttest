export type MapLayerId = 'street' | 'satellite'

export interface MapLayerOption {
  id: MapLayerId
  label: string
  mapTypeId: google.maps.MapTypeId
}

export const mapLayerOptions: MapLayerOption[] = [
  { id: 'street', label: 'Mapa', mapTypeId: 'roadmap' as google.maps.MapTypeId },
  { id: 'satellite', label: 'Sat\u00e9lite', mapTypeId: 'satellite' as google.maps.MapTypeId },
]

export function getAvailableTileProviders() {
  return mapLayerOptions
}

export function getGoogleMapType(id: MapLayerId) {
  return mapLayerOptions.find((option) => option.id === id)?.mapTypeId ?? ('roadmap' as google.maps.MapTypeId)
}
