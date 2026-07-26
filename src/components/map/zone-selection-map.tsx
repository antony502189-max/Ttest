import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Check, ChevronRight, MapPin, Pencil, Search, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MapLayerSwitcher } from '@/components/map/map-toolbar'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { loadTenerifeZoneHierarchy, loadTenerifeZones } from '@/lib/map/geojson'
import { getGoogleMapType, type MapLayerId } from '@/lib/map/providers'
import {
  TENERIFE_MUNICIPALITIES,
  canonicalizeZoneId,
  countListingsForZone,
  countListingsForZones,
  getZoneLabel,
  municipalityZoneId,
  type TenerifeZoneCollection,
  type TenerifeZoneFeature,
} from '@/lib/map/zones'
import { normalizeTenerifeText, TENERIFE_BOUNDS, TENERIFE_CENTER, TENERIFE_DEFAULT_ZOOM } from '@/lib/tenerife'
import type { Listing } from '@/types'
import '@/map.css'

export interface ZoneSelectionMapProps {
  selectedZoneIds: string[]
  listings: Listing[]
  onChange: (zoneIds: string[]) => void
  onApply?: () => void
  onDraw?: () => void
}

const EMPTY_FEATURES: TenerifeZoneFeature[] = []

function normalizeMunicipalities(collection: TenerifeZoneCollection): TenerifeZoneFeature[] {
  return collection.features.map((feature) => {
    const id = municipalityZoneId(feature.properties.id || feature.properties.label)
    return {
      ...feature,
      id,
      properties: { ...feature.properties, id, kind: 'municipality', geometryAvailable: true },
    }
  })
}

export function ZoneSelectionMap({ selectedZoneIds, listings, onChange, onApply, onDraw }: ZoneSelectionMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const featureByIdRef = useRef(new Map<string, google.maps.Data.Feature>())
  const onChangeRef = useRef(onChange)
  const selectedRef = useRef(selectedZoneIds.map(canonicalizeZoneId))
  const activeParentRef = useRef<string | null>(null)
  const [collection, setCollection] = useState<TenerifeZoneCollection | null>(null)
  const [term, setTerm] = useState('')
  const [activeParentId, setActiveParentId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [hierarchyNotice, setHierarchyNotice] = useState('')
  const [announcement, setAnnouncement] = useState('')
  const [layer, setLayer] = useState<MapLayerId>('street')
  const selectedIds = useMemo(() => selectedZoneIds.map(canonicalizeZoneId), [selectedZoneIds])
  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])
  const features = collection?.features ?? EMPTY_FEATURES
  const featureById = useMemo(() => new Map(features.map((feature) => [feature.properties.id, feature])), [features])
  const childrenByParent = useMemo(() => {
    const result = new Map<string | null, TenerifeZoneFeature[]>()
    features.forEach((feature) => {
      const parent = feature.properties.parentId ?? null
      result.set(parent, [...(result.get(parent) ?? []), feature])
    })
    result.forEach((items) => items.sort((a, b) => a.properties.label.localeCompare(b.properties.label, 'es')))
    return result
  }, [features])
  const rootOptions = useMemo(() => childrenByParent.get(null) ?? TENERIFE_MUNICIPALITIES.map((label) => ({
    type: 'Feature' as const,
    id: municipalityZoneId(label),
    properties: { id: municipalityZoneId(label), label, kind: 'municipality' as const, geometryAvailable: false },
    geometry: { type: 'Polygon' as const, coordinates: [] },
  })), [childrenByParent])
  const normalizedTerm = normalizeTenerifeText(term.trim())
  const visibleOptions = useMemo(() => {
    if (normalizedTerm) {
      return features.filter((feature) => {
        const values = [feature.properties.label, ...(feature.properties.aliases ?? [])]
        return values.some((value) => normalizeTenerifeText(value).includes(normalizedTerm))
      }).slice(0, 80)
    }
    return activeParentId ? childrenByParent.get(activeParentId) ?? [] : rootOptions
  }, [activeParentId, childrenByParent, features, normalizedTerm, rootOptions])
  const activeParent = activeParentId ? featureById.get(activeParentId) : undefined
  const parentOfActive = activeParent?.properties.parentId ?? null
  const resultCount = useMemo(() => countListingsForZones(listings, selectedIds, collection), [collection, listings, selectedIds])

  onChangeRef.current = onChange
  selectedRef.current = selectedIds
  activeParentRef.current = activeParentId

  const styleFor = useCallback((feature: google.maps.Data.Feature): google.maps.Data.StyleOptions => {
    const id = canonicalizeZoneId(String(feature.getProperty('id') ?? ''))
    const parentId = feature.getProperty('parentId') ? String(feature.getProperty('parentId')) : null
    const visible = activeParentRef.current ? parentId === activeParentRef.current : !parentId
    const selected = selectedRef.current.includes(id)
    return selected
      ? { visible, strokeColor: '#486600', strokeWeight: 3, fillColor: '#dfff45', fillOpacity: .38, zIndex: 3 }
      : { visible, strokeColor: '#3e4b46', strokeWeight: 1.3, fillColor: '#dfff45', fillOpacity: .06, zIndex: 1 }
  }, [])

  const toggleZone = useCallback((id: string, label = getZoneLabel(id)) => {
    const canonical = canonicalizeZoneId(id)
    const isSelected = selectedRef.current.includes(canonical)
    const next = isSelected ? selectedRef.current.filter((zoneId) => zoneId !== canonical) : [...selectedRef.current, canonical]
    onChangeRef.current(next)
    setAnnouncement(isSelected ? `${label} eliminada. ${next.length} zonas seleccionadas.` : `${label} seleccionada. ${next.length} zonas seleccionadas.`)
  }, [])

  const fitFeatures = useCallback((ids: string[]) => {
    const map = mapRef.current
    if (!map || !ids.length) return
    const bounds = new google.maps.LatLngBounds()
    ids.forEach((id) => featureByIdRef.current.get(id)?.getGeometry()?.forEachLatLng((point) => bounds.extend(point)))
    if (bounds.isEmpty()) return
    map.fitBounds(bounds, 28)
    google.maps.event.addListenerOnce(map, 'idle', () => {
      if ((map.getZoom() ?? 0) > 13) map.setZoom(13)
    })
  }, [])

  const openChildren = (feature: TenerifeZoneFeature) => {
    const children = childrenByParent.get(feature.properties.id) ?? []
    if (!children.length) {
      setHierarchyNotice(`No hay límites más detallados publicados para ${feature.properties.label}.`)
      return
    }
    setTerm('')
    setHierarchyNotice('')
    setActiveParentId(feature.properties.id)
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

    Promise.all([loadGoogleMaps(), loadTenerifeZones(), loadTenerifeZoneHierarchy().catch(() => null)]).then(([{ maps }, municipalities, hierarchy]) => {
      if (cancelled || !containerRef.current) return
      const municipalityFeatures = normalizeMunicipalities(municipalities)
      const combined: TenerifeZoneCollection = {
        type: 'FeatureCollection',
        attribution: 'Cabildo de Tenerife; ISTAC; Ayuntamiento de Santa Cruz de Tenerife',
        features: [...municipalityFeatures, ...(hierarchy?.features ?? [])],
        sources: hierarchy?.sources,
        retrieved: hierarchy?.retrieved,
      }
      setCollection(combined)
      if (!hierarchy) setHierarchyNotice('Los límites detallados no están disponibles ahora; se mantienen los 31 municipios.')
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
      const addedFeatures = map.data.addGeoJson(combined as never)
      const rootIds: string[] = []
      addedFeatures.forEach((feature) => {
        const id = canonicalizeZoneId(String(feature.getProperty('id') ?? ''))
        featureStore.set(id, feature)
        if (!feature.getProperty('parentId')) rootIds.push(id)
      })
      map.data.setStyle(styleFor)
      listeners.push(map.data.addListener('click', (event: google.maps.Data.MouseEvent) => {
        const id = canonicalizeZoneId(String(event.feature.getProperty('id') ?? ''))
        toggleZone(id, String(event.feature.getProperty('label') ?? id))
      }))
      listeners.push(map.data.addListener('mouseover', (event: google.maps.Data.MouseEvent) => {
        map.data.overrideStyle(event.feature, { strokeColor: '#486600', strokeWeight: 3, fillOpacity: .24 })
      }))
      listeners.push(map.data.addListener('mouseout', (event: google.maps.Data.MouseEvent) => map.data.revertStyle(event.feature)))
      fitFeatures(rootIds)
      resizeObserver = new ResizeObserver(() => {
        const center = map.getCenter()
        google.maps.event.trigger(map, 'resize')
        if (center) map.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)
      setLoading(false)
    }).catch((loadError) => {
      if (cancelled) return
      loadTenerifeZones().then((municipalities) => setCollection({ type: 'FeatureCollection', features: normalizeMunicipalities(municipalities) })).catch(() => undefined)
      setError(loadError instanceof GoogleMapsSetupError ? googleMapsErrorMessage(loadError) : 'No se pudieron cargar los límites geográficos.')
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
  }, [fitFeatures, styleFor, toggleZone])

  useEffect(() => {
    mapRef.current?.data.setStyle(styleFor)
  }, [activeParentId, selectedZoneIds, styleFor])

  useEffect(() => {
    if (!collection) return
    const ids = activeParentId
      ? collection.features.filter((feature) => feature.properties.parentId === activeParentId).map((feature) => feature.properties.id)
      : collection.features.filter((feature) => !feature.properties.parentId).map((feature) => feature.properties.id)
    fitFeatures(ids)
  }, [activeParentId, collection, fitFeatures])

  useEffect(() => {
    mapRef.current?.setMapTypeId(getGoogleMapType(layer))
  }, [layer])

  const focusZone = (id: string) => fitFeatures([canonicalizeZoneId(id)])

  return <section className="zone-selection" aria-label="Seleccionar zonas de Tenerife" data-provider="google-maps">
    <div className="zone-selection__sidebar">
      <label className="zone-selection__search"><Search aria-hidden="true" /><span className="sr-only">Buscar municipio, distrito o barrio</span><Input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Buscar municipio, distrito o barrio" /></label>
      <p className="zone-selection__rule"><Pencil aria-hidden="true" />Las zonas administrativas y la zona dibujada son alternativas. Aplicar una sustituye a la otra.</p>
      {!normalizedTerm && activeParent ? <nav className="zone-selection__breadcrumb" aria-label="Jerarquía de zonas">
        <button type="button" onClick={() => setActiveParentId(parentOfActive)}><ArrowLeft aria-hidden="true" />{activeParent.properties.label}</button>
      </nav> : null}
      {hierarchyNotice ? <p className="zone-selection__notice" role="status">{hierarchyNotice}</p> : null}
      <div className="zone-selection__list" role="group" aria-label={normalizedTerm ? 'Resultados de zonas' : activeParent ? `Zonas dentro de ${activeParent.properties.label}` : 'Municipios de Tenerife'}>
        {visibleOptions.map((zone) => {
          const { id, label } = zone.properties
          const selected = selectedSet.has(id)
          const children = childrenByParent.get(id) ?? []
          const count = countListingsForZone(listings, id, collection)
          return <div className="zone-selection__row" key={id}>
            <button type="button" className={selected ? 'is-selected' : ''} aria-pressed={selected} onClick={() => { toggleZone(id, label); focusZone(id) }} onFocus={() => focusZone(id)}><span className="zone-selection__check">{selected ? <Check aria-hidden="true" /> : <MapPin aria-hidden="true" />}</span><span><strong>{label}</strong><small>{zone.properties.kind === 'municipality' ? 'Municipio' : zone.properties.kind === 'district' ? 'Distrito' : 'Barrio'} · {count} habitaciones</small></span></button>
            {children.length ? <button type="button" className="zone-selection__drill" aria-label={`Ver zonas dentro de ${label}`} onClick={() => openChildren(zone)}><ChevronRight aria-hidden="true" /></button> : null}
          </div>
        })}
        {!visibleOptions.length ? <p className="zone-selection__empty">No hay zonas publicadas que coincidan.</p> : null}
      </div>
    </div>
    <div className="zone-selection__map-wrap google-map-shell">
      <div ref={containerRef} className="zone-selection__map google-map-canvas" role="application" aria-label="Google Maps con municipios, distritos y barrios de Tenerife" />
      <MapLayerSwitcher value={layer} onChange={setLayer} />
      {loading ? <div className="map-loading" role="status">Cargando límites administrativos…</div> : null}
      {error ? <div className="zone-selection__error" role="alert">{error} Puedes seguir usando la lista de zonas.</div> : null}
      <small className="zone-selection__attribution">Límites: Cabildo de Tenerife (CC BY), ISTAC y Ayuntamiento de Santa Cruz de Tenerife (CC BY)</small>
    </div>
    <div className="zone-selection__status" role="status" aria-live="polite">{announcement}</div>
    <footer className="zone-selection__footer">
      <div><strong>{selectedIds.length} {selectedIds.length === 1 ? 'zona seleccionada' : 'zonas seleccionadas'}</strong><span>{resultCount} {resultCount === 1 ? 'habitación disponible' : 'habitaciones disponibles'}</span></div>
      {onDraw ? <Button type="button" variant="outline" onClick={onDraw}><Pencil data-icon="inline-start" />Dibujar área</Button> : null}
      {selectedIds.length ? <Button type="button" variant="ghost" onClick={() => onChange([])}><X data-icon="inline-start" />Borrar</Button> : null}
      {onApply ? <Button type="button" onClick={onApply}>Ver {resultCount} {resultCount === 1 ? 'habitación' : 'habitaciones'}</Button> : null}
    </footer>
  </section>
}
