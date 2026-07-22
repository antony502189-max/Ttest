import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, MapPin, Pencil, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MapLayerSwitcher } from '@/components/map/map-toolbar'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { loadTenerifeZones } from '@/lib/map/geojson'
import { getGoogleMapType, type MapLayerId } from '@/lib/map/providers'
import { TENERIFE_MUNICIPALITIES, countListingsByMunicipality, countListingsForZones, getMunicipalityLabel, slugifyZone, type TenerifeZoneCollection } from '@/lib/map/zones'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, TENERIFE_DEFAULT_ZOOM } from '@/lib/tenerife'
import type { Listing } from '@/types'
import '@/map.css'

export interface ZoneSelectionMapProps {
  selectedZoneIds: string[]
  listings: Listing[]
  onChange: (zoneIds: string[]) => void
  onApply?: () => void
  onDraw?: () => void
}

export function ZoneSelectionMap({ selectedZoneIds, listings, onChange, onApply, onDraw }: ZoneSelectionMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const featureByIdRef = useRef(new Map<string, google.maps.Data.Feature>())
  const onChangeRef = useRef(onChange)
  const selectedRef = useRef(selectedZoneIds)
  const [zones, setZones] = useState<TenerifeZoneCollection['features']>([])
  const [term, setTerm] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [announcement, setAnnouncement] = useState('')
  const [layer, setLayer] = useState<MapLayerId>('street')
  const counts = useMemo(() => countListingsByMunicipality(listings), [listings])
  const resultCount = useMemo(() => countListingsForZones(listings, selectedZoneIds), [listings, selectedZoneIds])
  const selectedSet = useMemo(() => new Set(selectedZoneIds.map(slugifyZone)), [selectedZoneIds])
  const zoneOptions = useMemo(() => zones.length
    ? zones.map((zone) => zone.properties)
    : TENERIFE_MUNICIPALITIES.map((label) => ({ id: slugifyZone(label), label, kind: 'municipality' as const })), [zones])
  const filteredZones = useMemo(() => zoneOptions.filter((zone) => zone.label.toLocaleLowerCase('es-ES').includes(term.trim().toLocaleLowerCase('es-ES'))), [term, zoneOptions])

  onChangeRef.current = onChange
  selectedRef.current = selectedZoneIds

  const styleFor = (feature: google.maps.Data.Feature): google.maps.Data.StyleOptions => {
    const id = slugifyZone(String(feature.getProperty('id') ?? ''))
    const selected = selectedRef.current.map(slugifyZone).includes(id)
    return selected
      ? { strokeColor: '#486600', strokeWeight: 3, fillColor: '#dfff45', fillOpacity: .38, zIndex: 3 }
      : { strokeColor: '#3e4b46', strokeWeight: 1.3, fillColor: '#dfff45', fillOpacity: .06, zIndex: 1 }
  }

  const toggleZone = (id: string, label = getMunicipalityLabel(id) ?? id) => {
    const normalized = slugifyZone(id)
    const isSelected = selectedRef.current.map(slugifyZone).includes(normalized)
    const next = isSelected ? selectedRef.current.filter((zoneId) => slugifyZone(zoneId) !== normalized) : [...selectedRef.current, normalized]
    onChangeRef.current(next)
    setAnnouncement(isSelected ? `${label} eliminada. ${next.length} zonas seleccionadas.` : `${label} seleccionada. ${next.length} zonas seleccionadas.`)
  }

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let initializedMap: google.maps.Map | null = null
    const featureStore = featureByIdRef.current
    const listeners: google.maps.MapsEventListener[] = []
    const handleAuthFailure = () => setError(googleMapsAuthErrorMessage)
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)

    Promise.all([loadGoogleMaps(), loadTenerifeZones()]).then(([{ maps }, collection]) => {
      if (cancelled || !containerRef.current) return
      setZones(collection.features)
      const map = new maps.Map(containerRef.current, {
        center: TENERIFE_CENTER,
        zoom: TENERIFE_DEFAULT_ZOOM,
        minZoom: 8,
        maxZoom: 18,
        ...(googleMapsConfig.mapId ? { mapId: googleMapsConfig.mapId } : {}),
        mapTypeId: getGoogleMapType('street'),
        disableDefaultUI: true,
        zoomControl: true,
        clickableIcons: false,
        gestureHandling: 'greedy',
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: true },
      })
      mapRef.current = map
      initializedMap = map
      const features = map.data.addGeoJson(collection as never)
      const bounds = new google.maps.LatLngBounds()
      features.forEach((feature) => {
        const id = slugifyZone(String(feature.getProperty('id') ?? ''))
        featureStore.set(id, feature)
        feature.getGeometry()?.forEachLatLng((point) => bounds.extend(point))
      })
      map.data.setStyle(styleFor)
      listeners.push(map.data.addListener('click', (event: google.maps.Data.MouseEvent) => {
        const id = slugifyZone(String(event.feature.getProperty('id') ?? ''))
        toggleZone(id, String(event.feature.getProperty('label') ?? id))
      }))
      listeners.push(map.data.addListener('mouseover', (event: google.maps.Data.MouseEvent) => {
        map.data.overrideStyle(event.feature, { strokeColor: '#486600', strokeWeight: 3, fillOpacity: .24 })
      }))
      listeners.push(map.data.addListener('mouseout', (event: google.maps.Data.MouseEvent) => map.data.revertStyle(event.feature)))
      map.fitBounds(bounds, 24)
      resizeObserver = new ResizeObserver(() => {
        const center = map.getCenter()
        google.maps.event.trigger(map, 'resize')
        if (center) map.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)
      setLoading(false)
    }).catch((loadError) => {
      if (cancelled) return
      loadTenerifeZones().then((collection) => setZones(collection.features)).catch(() => undefined)
      setError(loadError instanceof GoogleMapsSetupError
        ? googleMapsErrorMessage(loadError)
        : 'No se pudieron cargar los l\u00edmites municipales.')
      setLoading(false)
    })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      listeners.forEach((listener) => listener.remove())
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
      if (initializedMap) google.maps.event.clearInstanceListeners(initializedMap)
      mapRef.current = null
      featureStore.clear()
      container.replaceChildren()
    }
  // The data layer reads selectedRef so it does not need to rebuild after every selection.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    mapRef.current?.data.setStyle(styleFor)
  }, [selectedZoneIds])

  useEffect(() => {
    mapRef.current?.setMapTypeId(getGoogleMapType(layer))
  }, [layer])

  const focusZone = (id: string) => {
    const feature = featureByIdRef.current.get(slugifyZone(id))
    const map = mapRef.current
    if (!feature || !map) return
    const bounds = new google.maps.LatLngBounds()
    feature.getGeometry()?.forEachLatLng((point) => bounds.extend(point))
    map.fitBounds(bounds, 36)
    map.setCenter(bounds.getCenter())
    google.maps.event.addListenerOnce(map, 'idle', () => {
      if ((map.getZoom() ?? 0) > 12) map.setZoom(12)
    })
  }

  return <section className="zone-selection" aria-label="Seleccionar municipios de Tenerife" data-provider="google-maps">
    <div className="zone-selection__sidebar">
      <label className="zone-selection__search"><Search aria-hidden="true" /><span className="sr-only">Buscar municipio</span><Input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Buscar municipio" /></label>
      <p className="zone-selection__rule"><Pencil aria-hidden="true" />Las zonas municipales y la zona dibujada son alternativas. Aplicar una sustituye a la otra.</p>
      <div className="zone-selection__list" role="group" aria-label="Municipios de Tenerife">
        {filteredZones.map((zone) => {
          const { id, label } = zone
          const selected = selectedSet.has(id)
          return <button key={id} type="button" className={selected ? 'is-selected' : ''} aria-pressed={selected} onClick={() => { toggleZone(id, label); focusZone(id) }} onFocus={() => focusZone(id)}><span className="zone-selection__check">{selected ? <Check aria-hidden="true" /> : <MapPin aria-hidden="true" />}</span><span><strong>{label}</strong><small>{counts.get(id) ?? 0} habitaciones</small></span></button>
        })}
      </div>
    </div>
    <div className="zone-selection__map-wrap google-map-shell">
      <div ref={containerRef} className="zone-selection__map google-map-canvas" role="application" aria-label="Google Maps con municipios de Tenerife" />
      <MapLayerSwitcher value={layer} onChange={setLayer} />
      {loading ? <div className="map-loading" role="status">Cargando límites municipales…</div> : null}
      {error ? <div className="zone-selection__error" role="alert">{error} Puedes seguir usando la lista de zonas.</div> : null}
      <small className="zone-selection__attribution">Límites municipales: Cabildo de Tenerife, CC BY</small>
    </div>
    <div className="zone-selection__status" role="status" aria-live="polite">{announcement}</div>
    <footer className="zone-selection__footer">
      <div><strong>{selectedZoneIds.length} {selectedZoneIds.length === 1 ? 'zona seleccionada' : 'zonas seleccionadas'}</strong><span>{resultCount} {resultCount === 1 ? 'habitaci\u00f3n disponible' : 'habitaciones disponibles'}</span></div>
      {onDraw ? <Button type="button" variant="outline" onClick={onDraw}><Pencil data-icon="inline-start" />Dibujar área</Button> : null}
      {selectedZoneIds.length ? <Button type="button" variant="ghost" onClick={() => onChange([])}><X data-icon="inline-start" />Borrar</Button> : null}
      {onApply ? <Button type="button" onClick={onApply}>Ver {resultCount} {resultCount === 1 ? 'habitaci\u00f3n' : 'habitaciones'}</Button> : null}
    </footer>
  </section>
}
