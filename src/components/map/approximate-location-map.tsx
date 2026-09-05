import { useEffect, useRef, useState } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'
import { createRequestVersionGate, parseGoogleAddress, type ResolvedGoogleAddress } from '@/lib/google-maps/address'

const DOUBLE_TAP_DELAY_MS = 360
const DOUBLE_TAP_DISTANCE_PX = 28
const TAP_MOVE_TOLERANCE_PX = 14
const DEFAULT_PUBLICATION_ZOOM = 11
const ADDRESS_SELECTION_ZOOM = 13

type ApproximateLocationMapProps = {
  coordinates: Coordinates
  onChange: (coordinates: Coordinates) => void
  onAddressResolved?: (address: ResolvedGoogleAddress) => void
  onLocationError?: (message: string) => void
}

type SelectedLocationDetail = {
  coordinates?: Coordinates
  zoom?: number
  clearDetectedAddress?: boolean
}

export function ApproximateLocationMap({ coordinates, onChange, onAddressResolved, onLocationError }: ApproximateLocationMapProps) {
  const { language } = useI18n()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const onChangeRef = useRef(onChange)
  const onAddressResolvedRef = useRef(onAddressResolved)
  const onLocationErrorRef = useRef(onLocationError)
  const initialCoordinatesRef = useRef(coordinates)
  const internalChangeRef = useRef(false)
  const requestGateRef = useRef(createRequestVersionGate())
  const [error, setError] = useState('')
  const [detectedAddress, setDetectedAddress] = useState('')
  const guidance = language === 'ru'
    ? 'Перемещайте карту пальцем и дважды коснитесь нужного места, чтобы поставить маркер.'
    : language === 'en'
      ? 'Move the map with your finger and double-tap the desired place to set the marker.'
      : 'Mueve el mapa con el dedo y toca dos veces el lugar deseado para colocar el marcador.'
  const mapLabel = language === 'ru'
    ? `Google Maps для выбора местоположения. ${guidance}`
    : language === 'en'
      ? `Google Maps for choosing a location. ${guidance}`
      : `Google Maps para elegir una ubicación. ${guidance}`
  const detectedLabel = language === 'ru' ? 'Определённый адрес' : language === 'en' ? 'Detected address' : 'Dirección detectada'

  useEffect(() => { onChangeRef.current = onChange }, [onChange])
  useEffect(() => { onAddressResolvedRef.current = onAddressResolved }, [onAddressResolved])
  useEffect(() => { onLocationErrorRef.current = onLocationError }, [onLocationError])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let dragListener: google.maps.MapsEventListener | null = null
    let mapDoubleClickListener: google.maps.MapsEventListener | null = null
    let removePointerListeners: (() => void) | null = null
    let pointerStart: { id: number; x: number; y: number } | null = null
    let lastTap: { at: number; x: number; y: number } | null = null
    let geocoder: google.maps.Geocoder | null = null
    const handleAuthFailure = () => setError(googleMapsAuthErrorMessage)
    const handleLocationError = (event: Event) => setError((event as CustomEvent<{ message?: string }>).detail?.message ?? 'No se pudo resolver esta dirección.')
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
    window.addEventListener('112233:publish-location-error', handleLocationError)

    loadGoogleMaps().then(async ({ maps, marker }) => {
      if (cancelled || !containerRef.current) return
      if (!googleMapsConfig.mapId) throw new GoogleMapsSetupError('missing-map-id')
      const requestedInitial = initialCoordinatesRef.current
      const initial = isInsideTenerife(requestedInitial) ? requestedInitial : TENERIFE_CENTER
      const mapInstance = new maps.Map(containerRef.current, {
        center: initial,
        zoom: DEFAULT_PUBLICATION_ZOOM,
        minZoom: 9,
        maxZoom: 20,
        mapId: googleMapsConfig.mapId,
        mapTypeId: 'roadmap',
        disableDefaultUI: true,
        zoomControl: true,
        clickableIcons: false,
        gestureHandling: 'greedy',
        disableDoubleClickZoom: true,
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: true },
      })
      mapInstance.setCenter(initial)
      mapInstance.setZoom(DEFAULT_PUBLICATION_ZOOM)
      const pin = new marker.PinElement({ background: '#dff34f', borderColor: '#344500', glyphColor: '#344500', scale: 1.15 })
      const publicMarker = new marker.AdvancedMarkerElement({ map: mapInstance, position: initial, content: pin, gmpDraggable: true, title: 'Ubicación seleccionada' })

      try {
        const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
        geocoder = new geocoding.Geocoder()
      } catch {
        // The map remains fully usable if geocoding is temporarily unavailable.
      }

      const resolveAddress = async (point: Coordinates) => {
        if (!geocoder || cancelled) return
        const version = requestGateRef.current.next()
        try {
          const response = await geocoder.geocode({ location: point })
          const result = response.results[0]
          if (!result || cancelled || !requestGateRef.current.isCurrent(version)) return
          setDetectedAddress(result.formatted_address)
          onAddressResolvedRef.current?.(parseGoogleAddress(result.address_components, result.formatted_address, point))
        } catch {
          if (!cancelled && requestGateRef.current.isCurrent(version)) onLocationErrorRef.current?.('No se pudo obtener la dirección de este punto. Puedes completar los campos manualmente.')
        }
      }

      const commitPoint = (point: Coordinates, detectAddress = true) => {
        if (!isInsideTenerife(point)) return
        publicMarker.position = point
        internalChangeRef.current = true
        onChangeRef.current(point)
        if (detectAddress) void resolveAddress(point)
      }

      const pointFromClientPosition = (clientX: number, clientY: number): Coordinates | null => {
        const projection = mapInstance.getProjection()
        const center = mapInstance.getCenter()
        const zoom = mapInstance.getZoom()
        if (!projection || !center || zoom == null) return null
        const centerWorld = projection.fromLatLngToPoint(center)
        if (!centerWorld) return null
        const rect = container.getBoundingClientRect()
        if (!rect.width || !rect.height) return null
        const scale = 2 ** zoom
        const worldPoint = new google.maps.Point(centerWorld.x + (clientX - rect.left - rect.width / 2) / scale, centerWorld.y + (clientY - rect.top - rect.height / 2) / scale)
        const latLng = projection.fromPointToLatLng(worldPoint)
        return latLng ? { lat: latLng.lat(), lng: latLng.lng() } : null
      }

      const placeFromClientPosition = (clientX: number, clientY: number) => {
        const point = pointFromClientPosition(clientX, clientY)
        if (point) commitPoint(point)
      }

      dragListener = publicMarker.addListener('dragend', () => {
        const position = publicMarker.position
        if (!position) return
        const point = position instanceof google.maps.LatLng ? { lat: position.lat(), lng: position.lng() } : { lat: position.lat, lng: position.lng }
        mapInstance.panTo(point)
        commitPoint(point)
      })
      mapDoubleClickListener = mapInstance.addListener('dblclick', (event: google.maps.MapMouseEvent) => {
        const latLng = event.latLng
        if (latLng) commitPoint({ lat: latLng.lat(), lng: latLng.lng() })
      })

      const handleSelectedLocation = (event: Event) => {
        const detail = (event as CustomEvent<SelectedLocationDetail>).detail ?? {}
        const point = detail.coordinates
        if (!point || !isInsideTenerife(point)) return
        requestGateRef.current.next()
        if (detail.clearDetectedAddress) setDetectedAddress('')
        const zoom = Math.max(9, Math.min(20, detail.zoom ?? ADDRESS_SELECTION_ZOOM))
        mapInstance.panTo(point)
        mapInstance.setZoom(zoom)
        commitPoint(point, false)
      }
      window.addEventListener('112233:publish-location-selected', handleSelectedLocation)

      const handleDoubleClick = (event: MouseEvent) => { event.preventDefault(); placeFromClientPosition(event.clientX, event.clientY) }
      const handlePointerDown = (event: PointerEvent) => { if (event.pointerType !== 'mouse') pointerStart = { id: event.pointerId, x: event.clientX, y: event.clientY } }
      const handlePointerUp = (event: PointerEvent) => {
        if (event.pointerType === 'mouse' || !pointerStart || pointerStart.id !== event.pointerId) return
        const moved = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y)
        pointerStart = null
        if (moved > TAP_MOVE_TOLERANCE_PX) { lastTap = null; return }
        const now = performance.now()
        if (lastTap && now - lastTap.at <= DOUBLE_TAP_DELAY_MS && Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) <= DOUBLE_TAP_DISTANCE_PX) {
          event.preventDefault(); placeFromClientPosition(event.clientX, event.clientY); lastTap = null; return
        }
        lastTap = { at: now, x: event.clientX, y: event.clientY }
      }
      const handlePointerCancel = () => { pointerStart = null; lastTap = null }

      container.addEventListener('dblclick', handleDoubleClick, true)
      container.addEventListener('pointerdown', handlePointerDown, true)
      container.addEventListener('pointerup', handlePointerUp, true)
      container.addEventListener('pointercancel', handlePointerCancel, true)
      removePointerListeners = () => {
        container.removeEventListener('dblclick', handleDoubleClick, true)
        container.removeEventListener('pointerdown', handlePointerDown, true)
        container.removeEventListener('pointerup', handlePointerUp, true)
        container.removeEventListener('pointercancel', handlePointerCancel, true)
        window.removeEventListener('112233:publish-location-selected', handleSelectedLocation)
      }

      mapRef.current = mapInstance
      markerRef.current = publicMarker
      resizeObserver = new ResizeObserver(() => { const center = mapInstance.getCenter(); google.maps.event.trigger(mapInstance, 'resize'); if (center) mapInstance.setCenter(center) })
      resizeObserver.observe(containerRef.current)
    }).catch((loadError) => { if (!cancelled) setError(googleMapsErrorMessage(loadError)) })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      dragListener?.remove()
      mapDoubleClickListener?.remove()
      removePointerListeners?.()
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
      window.removeEventListener('112233:publish-location-error', handleLocationError)
      if (markerRef.current) markerRef.current.map = null
      if (mapRef.current) google.maps.event.clearInstanceListeners(mapRef.current)
      mapRef.current = null
      markerRef.current = null
      container.replaceChildren()
    }
  }, [])

  useEffect(() => {
    if (!isInsideTenerife(coordinates)) return
    if (markerRef.current) markerRef.current.position = coordinates
    if (internalChangeRef.current) { internalChangeRef.current = false; return }
    requestGateRef.current.next()
    mapRef.current?.panTo(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="approximate-location-map-shell google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="approximate-location-map google-map-canvas" role="application" aria-label={mapLabel} />
    <p className="approximate-location-map-hint">{guidance}</p>
    {detectedAddress ? <p className="approximate-location-map-address" aria-live="polite"><strong>{detectedLabel}:</strong> {detectedAddress}</p> : null}
    {error ? <p className="map-inline-error" role="alert">{error}</p> : null}
  </div>
}
