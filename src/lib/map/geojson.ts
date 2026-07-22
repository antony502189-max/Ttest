import type { TenerifeZoneCollection } from '@/lib/map/zones'

const zoneDataUrl = new URL('../../data/maps/tenerife-municipalities.geojson', import.meta.url).href
let collectionPromise: Promise<TenerifeZoneCollection> | null = null

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
