import { useEffect, useMemo, useRef, useState } from 'react'
import { MarkerClusterer, SuperClusterAlgorithm } from '@googlemaps/markerclusterer'
import { MapPin } from 'lucide-react'
import { toast } from 'sonner'
import { useApp } from '@/contexts/app-context'
import { getPrimaryPrice } from '@/lib/listings'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { getGoogleMapType, type MapLayerId } from '@/lib/map/providers'
import { loadTenerifeZoneHierarchy, loadTenerifeZones } from '@/lib/map/geojson'
import { canonicalizeZoneId, municipalityZoneId } from '@/lib/map/zones'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, TENERIFE_DEFAULT_ZOOM, isInsideTenerife } from '@/lib/tenerife'
import { AdvancedClusterRenderer, createPriceMarkerContent, priceLabel, setPriceMarkerState } from '@/components/map/map-icons'
import { MapLayerSwitcher, MapToolbar } from '@/components/map/map-toolbar'
import { SelectedListingSheet } from '@/components/map/selected-listing-sheet'
import { cn } from '@/lib/utils'
import type { Listing, MapPolygonPoint } from '@/types'
import '@/map.css'

export interface MapBounds {
  north: number
  south: number
  east: number
  west: number
}

export interface ResultsMapProps {
  items: Listing[]
  selectedId?: string
  highlightedId?: string
  onSelect: (id: string) => void
  onHighlight?: (id: string) => void
  fullScreen?: boolean
  showPreview?: boolean
  onBoundsSearch?: (bounds: MapBounds) => void
  onPolygonSearch?: (polygon: MapPolygonPoint[]) => void
  onDrawingStart?: () => boolean | void
  fitResultsKey?: number
  initialAction?: 'draw' | 'near' | null
  onInitialActionHandled?: () => void
}

const boundsAreEqual = (left: MapBounds, right: MapBounds) =>
  (Object.keys(left) as (keyof MapBounds)[]).every((key) => Math.abs(left[key] - right[key]) < 0.00001)

const getMapBounds = (map: google.maps.Map): MapBounds | null => {
  const current = map.getBounds()
  if (!current) return null
  const northEast = current.getNorthEast()
  const southWest = current.getSouthWest()
  return { north: northEast.lat(), east: northEast.lng(), south: southWest.lat(), west: southWest.lng() }
}

function fitListings(map: google.maps.Map, listings: Listing[]) {
  if (!listings.length) return
  const bounds = new google.maps.LatLngBounds()
  listings.forEach((listing) => bounds.extend(listing.coordinates))
  const isCompact = map.getDiv().clientWidth < 768
  map.fitBounds(bounds, isCompact
    ? { top: 96, right: 42, bottom: 118, left: 42 }
    : { top: 72, right: 72, bottom: 72, left: 72 })
  // Google may animate fitBounds differently while a split pane is settling.
  // Pinning the computed center keeps desktop and mobile geometry deterministic.
  map.setCenter(bounds.getCenter())
  google.maps.event.addListenerOnce(map, 'idle', () => {
    const zoom = map.getZoom() ?? 0
    if (zoom > 13) map.setZoom(13)
    else if (isCompact && zoom < 9.65) map.setZoom(9.65)
  })
}

export function ResultsMap({ items, selectedId, highlightedId, onSelect, onHighlight, fullScreen = false, showPreview = true, onBoundsSearch, onPolygonSearch, onDrawingStart, fitResultsKey = 0, initialAction = null, onInitialActionHandled }: ResultsMapProps) {
  const { filters, mapPolygon, setMapPolygon, clearMapPolygon } = useApp()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const clusterRef = useRef<MarkerClusterer | null>(null)
  const markersRef = useRef(new Map<string, google.maps.marker.AdvancedMarkerElement>())
  const markerContentRef = useRef(new Map<string, HTMLElement>())
  const drawingLayerRef = useRef<google.maps.Polygon | google.maps.Polyline | null>(null)
  const vertexMarkersRef = useRef<google.maps.marker.AdvancedMarkerElement[]>([])
  const drawingRef = useRef(false)
  const onSelectRef = useRef(onSelect)
  const onHighlightRef = useRef(onHighlight)
  const itemsRef = useRef(items)
  const selectedIdRef = useRef(selectedId)
  const highlightedIdRef = useRef(highlightedId)
  const programmaticMoveRef = useRef(true)
  const fittedResultsRef = useRef(false)
  const skipNextResultsFitRef = useRef(false)
  const manualMovePendingRef = useRef(false)
  const lastSearchedBoundsRef = useRef<MapBounds | null>(null)
  const previousFitResultsKeyRef = useRef(fitResultsKey)
  const fittedPolygonSignatureRef = useRef('')
  const actionHandledRef = useRef(false)
  const geolocationPendingRef = useRef(false)
  const announcementRef = useRef<HTMLDivElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)
  const [drawing, setDrawing] = useState(false)
  const [drawSession, setDrawSession] = useState(false)
  const [draftPolygon, setDraftPolygon] = useState<MapPolygonPoint[]>(mapPolygon)
  const [bounds, setBounds] = useState<MapBounds | null>(null)
  const [ready, setReady] = useState(false)
  const [mapError, setMapError] = useState('')
  const [boundsDirty, setBoundsDirty] = useState(false)
  const [actionAnnouncement, setActionAnnouncement] = useState('')
  const [layer, setLayer] = useState<MapLayerId>('street')
  const [focusSheetOnOpen, setFocusSheetOnOpen] = useState(false)

  const selected = items.find((item) => item.id === selectedId)
  const itemSignature = useMemo(() => items.map((item) => `${item.id}:${item.coordinates.lat}:${item.coordinates.lng}:${getPrimaryPrice(item)}`).join('|'), [items])
  const selectedAreaSignature = filters.areas.map(canonicalizeZoneId).sort().join('|')
  itemsRef.current = items
  selectedIdRef.current = selectedId
  highlightedIdRef.current = highlightedId

  useEffect(() => { onSelectRef.current = onSelect }, [onSelect])
  useEffect(() => { onHighlightRef.current = onHighlight }, [onHighlight])
  useEffect(() => { drawingRef.current = drawing }, [drawing])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let initializedMap: google.maps.Map | null = null
    const listeners: google.maps.MapsEventListener[] = []
    const markZoomIntent = () => {
      programmaticMoveRef.current = false
      manualMovePendingRef.current = true
      setBoundsDirty(true)
    }
    const markKeyboardZoomIntent = (event: KeyboardEvent) => {
      if (event.key === '+' || event.key === '-' || event.key === '=') {
        programmaticMoveRef.current = false
        manualMovePendingRef.current = true
      }
    }
    const handleAuthFailure = () => setMapError(googleMapsAuthErrorMessage)
    container.addEventListener('wheel', markZoomIntent, { capture: true, passive: true })
    container.addEventListener('keydown', markKeyboardZoomIntent)
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)

    const loadTimeout = window.setTimeout(() => {
      if (!cancelled && !mapRef.current) setMapError(googleMapsErrorMessage(new GoogleMapsSetupError('load-failed')))
    }, 10_000)
    loadGoogleMaps().then(({ maps }) => {
      if (cancelled || !containerRef.current) return
      window.clearTimeout(loadTimeout)
      if (!googleMapsConfig.mapId) throw new GoogleMapsSetupError('missing-map-id')
      const map = new maps.Map(containerRef.current, {
        center: TENERIFE_CENTER,
        zoom: TENERIFE_DEFAULT_ZOOM,
        minZoom: 8,
        maxZoom: 19,
        mapId: googleMapsConfig.mapId,
        mapTypeId: getGoogleMapType('street'),
        disableDefaultUI: true,
        clickableIcons: false,
        keyboardShortcuts: true,
        gestureHandling: 'greedy',
        restriction: {
          latLngBounds: TENERIFE_BOUNDS,
          // A hard restriction forces a tall mobile viewport to zoom into only
          // half of Tenerife. Keep the island as a soft pan boundary so the
          // initial fit can show the complete result set like a property map.
          strictBounds: false,
        },
      })
      mapRef.current = map
      initializedMap = map
      containerRef.current.dataset.mapInstance = 'google-ready'

      const updateBounds = () => {
        const next = getMapBounds(map)
        const center = map.getCenter()
        if (next) setBounds(next)
        if (containerRef.current && center) {
          containerRef.current.dataset.mapCenter = `${center.lat().toFixed(6)},${center.lng().toFixed(6)}`
          containerRef.current.dataset.mapZoom = String(map.getZoom() ?? '')
        }
        if (manualMovePendingRef.current && !programmaticMoveRef.current) {
          manualMovePendingRef.current = false
          setBoundsDirty(true)
        }
      }
      const markManualMove = () => {
        programmaticMoveRef.current = false
        manualMovePendingRef.current = true
        setBoundsDirty(true)
      }
      listeners.push(map.addListener('idle', updateBounds))
      listeners.push(map.addListener('dragstart', markManualMove))
      listeners.push(map.addListener('click', (event: google.maps.MapMouseEvent) => {
        if (!drawingRef.current || !event.latLng) return
        setDraftPolygon((current) => [...current, { lat: event.latLng!.lat(), lng: event.latLng!.lng() }])
      }))
      resizeObserver = new ResizeObserver(() => {
        const center = fittedResultsRef.current ? map.getCenter() : null
        google.maps.event.trigger(map, 'resize')
        if (center) map.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)
      setReady(true)
      setMapError('')
      google.maps.event.addListenerOnce(map, 'idle', updateBounds)
      listeners.push(google.maps.event.addListenerOnce(map, 'idle', () => {
        if (cancelled || !itemsRef.current.length) return
        programmaticMoveRef.current = true
        fitListings(map, itemsRef.current)
        google.maps.event.addListenerOnce(map, 'idle', () => {
          fittedResultsRef.current = true
          programmaticMoveRef.current = false
        })
      }))
    }).catch((error) => {
      window.clearTimeout(loadTimeout)
      if (!cancelled) setMapError(googleMapsErrorMessage(error))
    })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      listeners.forEach((listener) => listener.remove())
      window.clearTimeout(loadTimeout)
      container.removeEventListener('wheel', markZoomIntent, true)
      container.removeEventListener('keydown', markKeyboardZoomIntent)
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
      if (initializedMap) google.maps.event.clearInstanceListeners(initializedMap)
      mapRef.current = null
      fittedResultsRef.current = false
      container.replaceChildren()
    }
  }, [])

  useEffect(() => {
    mapRef.current?.setMapTypeId(getGoogleMapType(layer))
  }, [layer])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    clusterRef.current?.clearMarkers()
    clusterRef.current?.setMap(null)
    markersRef.current.forEach((marker) => {
      google.maps.event.clearInstanceListeners(marker)
      marker.map = null
    })
    markersRef.current.clear()
    markerContentRef.current.clear()

    const markers = itemsRef.current.map((listing) => {
      const content = createPriceMarkerContent(listing)
      setPriceMarkerState(content, listing.id === selectedIdRef.current, listing.id === highlightedIdRef.current)
      content.dataset.markerZIndex = listing.id === selectedIdRef.current ? '3000' : '10'
      const marker = new google.maps.marker.AdvancedMarkerElement({
        position: listing.coordinates,
        content,
        title: `${listing.area}, ${priceLabel(listing)}`,
        gmpClickable: true,
        collisionBehavior: google.maps.CollisionBehavior.OPTIONAL_AND_HIDES_LOWER_PRIORITY,
        zIndex: listing.id === selectedIdRef.current ? 3000 : 10,
      })
      const select = (original: Event) => {
        setFocusSheetOnOpen(original instanceof KeyboardEvent || (original instanceof MouseEvent && original.detail === 0))
        returnFocusRef.current = original.target instanceof HTMLElement ? original.target : content
        onSelectRef.current(listing.id)
      }
      marker.addEventListener('gmp-click', select)
      content.addEventListener('mouseenter', () => onHighlightRef.current?.(listing.id))
      content.addEventListener('mouseleave', () => onHighlightRef.current?.(''))
      content.addEventListener('focus', () => onHighlightRef.current?.(listing.id))
      content.addEventListener('blur', () => onHighlightRef.current?.(''))
      markersRef.current.set(listing.id, marker)
      markerContentRef.current.set(listing.id, content)
      return marker
    })

    const cluster = new MarkerClusterer({
      map,
      markers,
      algorithm: new SuperClusterAlgorithm({ radius: 58, maxZoom: 16 }),
      renderer: new AdvancedClusterRenderer(),
    })
    clusterRef.current = cluster
    if (itemsRef.current.length && !skipNextResultsFitRef.current) {
      programmaticMoveRef.current = true
      fitListings(map, itemsRef.current)
      google.maps.event.addListenerOnce(map, 'idle', () => {
        fittedResultsRef.current = true
        programmaticMoveRef.current = false
      })
    } else if (skipNextResultsFitRef.current) {
      skipNextResultsFitRef.current = false
    }
    return () => {
      cluster.clearMarkers()
      cluster.setMap(null)
    }
  }, [itemSignature, ready])

  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const content = markerContentRef.current.get(id)
      if (content) {
        setPriceMarkerState(content, id === selectedId, id === highlightedId)
        content.dataset.markerZIndex = id === selectedId ? '3000' : id === highlightedId ? '2000' : '10'
      }
      marker.zIndex = id === selectedId ? 3000 : id === highlightedId ? 2000 : 10
    })
    const map = mapRef.current
    const clusterer = clusterRef.current
    if (!map || !clusterer) return
    const applyClusterState = () => {
      containerRef.current?.querySelectorAll('.map-cluster-marker.is-highlighted, .map-cluster-marker.is-selected').forEach((node) => node.classList.remove('is-highlighted', 'is-selected'))
      const clusters = (clusterer as unknown as { clusters: Array<{ marker?: google.maps.Marker | google.maps.marker.AdvancedMarkerElement; markers: Array<google.maps.Marker | google.maps.marker.AdvancedMarkerElement> }> }).clusters
      ;([{ id: highlightedId, className: 'is-highlighted' }, { id: selectedId, className: 'is-selected' }] as const).forEach(({ id, className }) => {
        const listingMarker = id ? markersRef.current.get(id) : undefined
        if (!listingMarker) return
        const cluster = clusters.find((candidate) => candidate.markers.length > 1 && candidate.markers.includes(listingMarker))
        if (!(cluster?.marker instanceof google.maps.marker.AdvancedMarkerElement)) return
        const content = cluster.marker.content
        if (content instanceof HTMLElement) content.querySelector('.map-cluster-marker')?.classList.add(className)
      })
    }
    applyClusterState()
    const idleListener = map.addListener('idle', applyClusterState)
    const clusterListener = google.maps.event.addListener(clusterer, 'clusteringend', applyClusterState)
    return () => {
      idleListener.remove()
      clusterListener.remove()
    }
  }, [highlightedId, itemSignature, ready, selectedId])

  useEffect(() => {
    const previous = previousFitResultsKeyRef.current
    previousFitResultsKeyRef.current = fitResultsKey
    const map = mapRef.current
    if (previous === fitResultsKey || !map || !itemsRef.current.length) return
    programmaticMoveRef.current = true
    setBoundsDirty(false)
    fitListings(map, itemsRef.current)
    google.maps.event.addListenerOnce(map, 'idle', () => { programmaticMoveRef.current = false })
  }, [fitResultsKey])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    let cancelled = false
    map.data.forEach((feature) => map.data.remove(feature))
    if (!selectedAreaSignature) return
    Promise.all([loadTenerifeZones(), loadTenerifeZoneHierarchy().catch(() => null)]).then(([municipalities, hierarchy]) => {
      if (cancelled || !mapRef.current) return
      const selectedAreas = new Set(selectedAreaSignature.split('|'))
      const municipalityFeatures = municipalities.features.map((feature) => ({
        ...feature,
        id: municipalityZoneId(feature.properties.id || feature.properties.label),
        properties: { ...feature.properties, id: municipalityZoneId(feature.properties.id || feature.properties.label) },
      }))
      map.data.addGeoJson({ type: 'FeatureCollection', features: [...municipalityFeatures, ...(hierarchy?.features ?? [])] } as unknown as GeoJSON.GeoJsonObject)
      map.data.setStyle((feature) => {
        const selectedArea = selectedAreas.has(canonicalizeZoneId(String(feature.getProperty('id') ?? '')))
        return {
          visible: selectedArea,
          fillColor: '#c51a84',
          fillOpacity: .2,
          strokeColor: '#9e176d',
          strokeOpacity: 1,
          strokeWeight: 3,
          zIndex: 2,
        }
      })
    }).catch(() => {
      if (!cancelled) setMapError('No se pudieron cargar los l\u00edmites seleccionados. El resto del mapa sigue disponible.')
    })
    return () => { cancelled = true }
  }, [ready, selectedAreaSignature])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    drawingLayerRef.current?.setMap(null)
    drawingLayerRef.current = null
    vertexMarkersRef.current.forEach((marker) => { marker.map = null })
    vertexMarkersRef.current = []
    if (draftPolygon.length >= 3) {
      drawingLayerRef.current = new google.maps.Polygon({
        map,
        paths: draftPolygon,
        clickable: false,
        strokeColor: '#9e176d',
        strokeOpacity: 1,
        strokeWeight: 3,
        fillColor: '#c51a84',
        fillOpacity: .22,
        zIndex: 5,
      })
    } else if (draftPolygon.length >= 2) {
      drawingLayerRef.current = new google.maps.Polyline({ map, path: draftPolygon, clickable: false, strokeColor: '#9e176d', strokeWeight: 3, zIndex: 5 })
    }
    if (drawing) {
      vertexMarkersRef.current = draftPolygon.map((position, index) => {
        const point = document.createElement('span')
        point.className = 'map-drawing-vertex'
        point.textContent = String(index + 1)
        return new google.maps.marker.AdvancedMarkerElement({ map, position, content: point, zIndex: 4000 + index })
      })
    }
    return () => {
      drawingLayerRef.current?.setMap(null)
      vertexMarkersRef.current.forEach((marker) => { marker.map = null })
    }
  }, [draftPolygon, drawing, ready])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready || mapPolygon.length < 3) return
    const signature = mapPolygon.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join(';')
    if (fittedPolygonSignatureRef.current === signature) return
    fittedPolygonSignatureRef.current = signature
    const polygonBounds = new google.maps.LatLngBounds()
    mapPolygon.forEach((point) => polygonBounds.extend(point))
    programmaticMoveRef.current = true
    setBoundsDirty(false)
    map.fitBounds(polygonBounds, { top: 72, right: 32, bottom: 96, left: 32 })
    google.maps.event.addListenerOnce(map, 'idle', () => { programmaticMoveRef.current = false })
  }, [mapPolygon, ready])

  const startDrawing = () => {
    if (onDrawingStart?.() === false) return
    onSelectRef.current('')
    setFocusSheetOnOpen(false)
    setDraftPolygon([])
    setDrawSession(true)
    setDrawing(true)
    setActionAnnouncement('Modo dibujo activado. La zona dibujada sustituye a las zonas municipales. A\u00f1ade al menos 3 puntos.')
  }
  const cancelDrawing = () => { setDraftPolygon(mapPolygon); setDrawing(false); setDrawSession(false) }
  const addKeyboardPoint = () => {
    const map = mapRef.current
    const center = map?.getCenter()
    if (!center) return
    const offsets = [[-.08, -.08], [.08, -.08], [0, .09], [-.08, .08]]
    const offset = offsets[draftPolygon.length % offsets.length]
    setDraftPolygon((current) => [...current, { lat: center.lat() + offset[0], lng: center.lng() + offset[1] }])
  }
  const finishDrawing = () => {
    if (draftPolygon.length < 3) return
    setDrawing(false)
    setMapPolygon(draftPolygon)
    onPolygonSearch?.(draftPolygon)
    setActionAnnouncement(`Zona dibujada aplicada con ${draftPolygon.length} puntos.`)
    toast.success(`Zona aplicada: ${draftPolygon.length} puntos`)
  }
  const deletePolygon = () => {
    setDraftPolygon([])
    clearMapPolygon()
    onPolygonSearch?.([])
    setDrawSession(false)
    setActionAnnouncement('Zona dibujada eliminada.')
  }
  const locateCurrentPosition = () => {
    if (!navigator.geolocation) { toast.error('Tu navegador no ofrece geolocalizaci\u00f3n'); return }
    if (geolocationPendingRef.current) return
    geolocationPendingRef.current = true
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      geolocationPendingRef.current = false
      const current = { lat: coords.latitude, lng: coords.longitude }
      if (!isInsideTenerife(current)) {
        setActionAnnouncement('Tu ubicaci\u00f3n est\u00e1 fuera de Tenerife. El mapa permanece en la isla.')
        toast.error('Tu ubicaci\u00f3n est\u00e1 fuera de Tenerife.')
        return
      }
      programmaticMoveRef.current = true
      mapRef.current?.setCenter(current)
      mapRef.current?.setZoom(14)
      if (mapRef.current) google.maps.event.addListenerOnce(mapRef.current, 'idle', () => { programmaticMoveRef.current = false })
      setActionAnnouncement('Ubicaci\u00f3n encontrada en Tenerife.')
    }, () => {
      geolocationPendingRef.current = false
      setActionAnnouncement('No pudimos obtener tu ubicaci\u00f3n. Puedes mover el mapa manualmente.')
      toast.error('No pudimos obtener tu ubicaci\u00f3n.')
    }, { timeout: 7000 })
  }
  const searchBounds = () => {
    const currentBounds = mapRef.current ? getMapBounds(mapRef.current) : bounds
    if (!currentBounds || !onBoundsSearch || !boundsDirty) return
    if (lastSearchedBoundsRef.current && boundsAreEqual(currentBounds, lastSearchedBoundsRef.current)) { setBoundsDirty(false); return }
    skipNextResultsFitRef.current = true
    onBoundsSearch(currentBounds)
    lastSearchedBoundsRef.current = currentBounds
    setBoundsDirty(false)
    setActionAnnouncement('Resultados actualizados para el \u00e1rea visible.')
  }

  const markManualMapInteraction = () => {
    programmaticMoveRef.current = false
    manualMovePendingRef.current = true
    setBoundsDirty(true)
  }

  useEffect(() => {
    if (!initialAction) { actionHandledRef.current = false; return }
    if (!ready || actionHandledRef.current) return
    actionHandledRef.current = true
    if (initialAction === 'draw') startDrawing()
    else locateCurrentPosition()
    onInitialActionHandled?.()
  // The action token and readiness intentionally control this one-shot effect.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAction, onInitialActionHandled, ready])

  return <section className={cn('results-map google-map-shell', fullScreen && 'results-map--fullscreen google-map-shell--fullscreen', selected && 'has-selection', drawing && 'is-drawing', drawSession && 'is-draw-session', mapPolygon.length >= 3 && 'has-polygon', mapError && 'has-map-error')} aria-label="Mapa de resultados" data-drawing={drawing || undefined} data-provider="google-maps" onWheelCapture={markManualMapInteraction}>
    <div className="results-map__canvas google-map-canvas" ref={containerRef} role="application" aria-label="Google Maps con precios de habitaciones" />
    <MapLayerSwitcher value={layer} onChange={setLayer} />
    {fullScreen ? <MapToolbar boundsDirty={boundsDirty} canSearchBounds={Boolean(boundsDirty && bounds && onBoundsSearch)} drawing={drawing} pointCount={draftPolygon.length} hasPolygon={mapPolygon.length >= 3} onSearchBounds={searchBounds} onLocate={locateCurrentPosition} onStartDrawing={startDrawing} onAddPoint={addKeyboardPoint} onCancelDrawing={cancelDrawing} onFinishDrawing={finishDrawing} onDeletePolygon={deletePolygon} /> : null}
    {actionAnnouncement ? <div ref={announcementRef} className="map-action-announcement" role="status" aria-live="polite" tabIndex={-1}>{actionAnnouncement}</div> : null}
    {!ready && !mapError ? <div className="map-loading" role="status" aria-live="polite"><span aria-hidden="true" /><strong>Cargando Google Maps</strong></div> : null}
    {googleMapsConfig.usesDevelopmentMapId ? <p className="map-dev-notice">Mapa de desarrollo: configura un Map ID propio antes de publicar.</p> : null}
    {mapError ? <div className="map-inline-error" role="alert"><strong>Mapa no disponible</strong><span>{mapError}</span></div> : null}
    {selected && showPreview ? <SelectedListingSheet listing={selected} focusOnOpen={focusSheetOnOpen} returnFocus={returnFocusRef.current} onClose={() => { setFocusSheetOnOpen(false); onSelect('') }} /> : null}
    <div className="map-list-alternative" aria-label="Alternativa textual al mapa">
      {items.map((item) => <button key={item.id} type="button" onFocus={() => onHighlight?.(item.id)} onMouseEnter={() => onHighlight?.(item.id)} onClick={() => onSelect(item.id)} aria-pressed={item.id === selectedId}><MapPin aria-hidden="true" /><span><strong>{item.area}</strong><small>{priceLabel(item)}</small></span></button>)}
    </div>
  </section>
}
