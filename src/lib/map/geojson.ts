import type { TenerifeZoneCollection } from '@/lib/map/zones'

const zoneDataUrl = new URL('../../data/maps/tenerife-municipalities.geojson', import.meta.url).href
const hierarchyDataUrl = new URL('../../data/maps/tenerife-zone-hierarchy.geojson', import.meta.url).href
let collectionPromise: Promise<TenerifeZoneCollection> | null = null
let hierarchyPromise: Promise<TenerifeZoneCollection> | null = null

export function loadTenerifeZones() {
  if (!collectionPromise) {
    collectionPromise = fetch(zoneDataUrl).then((response) => {
      if (!response.ok) throw new Error(`GeoJSON ${response.status}`)
      return response.json() as Promise<TenerifeZoneCollection>
    }).catch((error) => {
      collectionPromise = null
      throw error
    })
  }
  return collectionPromise
}

export function loadTenerifeZoneHierarchy() {
  if (!hierarchyPromise) {
    hierarchyPromise = fetch(hierarchyDataUrl).then((response) => {
      if (!response.ok) throw new Error(`Zone hierarchy GeoJSON ${response.status}`)
      return response.json() as Promise<TenerifeZoneCollection>
    }).catch((error) => {
      hierarchyPromise = null
      throw error
    })
  }
  return hierarchyPromise
}
