import { useEffect, useRef, useState } from 'react'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

const DOUBLE_TAP_DELAY_MS = 360
const DOUBLE_TAP_DISTANCE_PX = 28
const TAP_MOVE_TOLERANCE_PX = 14

export function ApproximateLocationMap({ coordinates, onChange }: { coordinates: Coordinates; onChange: (coordinates: Coordinates) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const onChangeRef = useRef(onChange)
  const initialCoordinatesRef = useRef(coordinates)
  const internalChangeRef = useRef(false)
  const [error, setError] = useState('')

  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let dragListener: google.maps.MapsEventListener | null = null
    let mapDoubleClickListener: google.maps.MapsEventListener | null = null
    let pointerStart: { id: number; x: number; y: number } | null = null
    let lastTap: { at: number; x: number; y: number } | null = null
    const handleAuthFailure = () => setError(googleMapsAuthErrorMessage)
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)

    loadGoogleMaps().then(({ maps, marker }) => {
      if (cancelled || !containerRef.current) return
      if (!googleMapsConfig.mapId) throw new GoogleMapsSetupError('missing-map-id')
      const requestedInitial = initialCoordinatesRef.current
      const initial = isInsideTenerife(requestedInitial) ? requestedInitial : TENERIFE_CENTER
      const mapInstance = new maps.Map(containerRef.current, {
        center: initial,
        zoom: 14,
        minZoom: 10,
        maxZoom: 18,
        mapId: googleMapsConfig.mapId,
        disableDefaultUI: true,
        zoomControl: true,
        clickableIcons: false,
        gestureHandling: 'greedy',
        disableDoubleClickZoom: true,
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: true },
      })
      const pin = new marker.PinElement({ background: '#dff34f', borderColor: '#344500', glyphColor: '#344500', scale: 1.15 })
      const publicMarker = new marker.AdvancedMarkerElement({
        map: mapInstance,
        position: initial,
        content: pin,
        gmpDraggable: true,
        title: 'Ubicación pública aproximada',
      })

      const commitPoint = (point: Coordinates) => {
        if (!isInsideTenerife(point)) return
        publicMarker.position = point
        internalChangeRef.current = true
        onChangeRef.current(point)
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
        const worldPoint = new google.maps.Point(
          centerWorld.x + (clientX - rect.left - rect.width / 2) / scale,
          centerWorld.y + (clientY - rect.top - rect.height / 2) / scale,
        )
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
        const point = position instanceof google.maps.LatLng
          ? { lat: position.lat(), lng: position.lng() }
          : { lat: position.lat, lng: position.lng }
        commitPoint(point)
      })

      mapDoubleClickListener = mapInstance.addListener('dblclick', (event: google.maps.MapMouseEvent) => {
        const latLng = event.latLng
        if (latLng) commitPoint({ lat: latLng.lat(), lng: latLng.lng() })
      })

      const handleDoubleClick = (event: MouseEvent) => {
        event.preventDefault()
        placeFromClientPosition(event.clientX, event.clientY)
      }
      const handlePointerDown = (event: PointerEvent) => {
        if (event.pointerType === 'mouse') return
        pointerStart = { id: event.pointerId, x: event.clientX, y: event.clientY }
      }
      const handlePointerUp = (event: PointerEvent) => {
        if (event.pointerType === 'mouse' || !pointerStart || pointerStart.id !== event.pointerId) return
        const moved = Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y)
        pointerStart = null
        if (moved > TAP_MOVE_TOLERANCE_PX) {
          lastTap = null
          return
        }
        const now = performance.now()
        if (lastTap && now - lastTap.at <= DOUBLE_TAP_DELAY_MS && Math.hypot(event.clientX - lastTap.x, event.clientY - lastTap.y) <= DOUBLE_TAP_DISTANCE_PX) {
          event.preventDefault()
          placeFromClientPosition(event.clientX, event.clientY)
          lastTap = null
          return
        }
        lastTap = { at: now, x: event.clientX, y: event.clientY }
      }
      const handlePointerCancel = () => {
        pointerStart = null
        lastTap = null
      }

      container.addEventListener('dblclick', handleDoubleClick, true)
      container.addEventListener('pointerdown', handlePointerDown, true)
      container.addEventListener('pointerup', handlePointerUp, true)
      container.addEventListener('pointercancel', handlePointerCancel, true)

      mapRef.current = mapInstance
      markerRef.current = publicMarker
      resizeObserver = new ResizeObserver(() => {
        const center = mapInstance.getCenter()
        google.maps.event.trigger(mapInstance, 'resize')
        if (center) mapInstance.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)

      return () => {
        container.removeEventListener('dblclick', handleDoubleClick, true)
        container.removeEventListener('pointerdown', handlePointerDown, true)
        container.removeEventListener('pointerup', handlePointerUp, true)
        container.removeEventListener('pointercancel', handlePointerCancel, true)
      }
    }).then((removePointerListeners) => {
      if (cancelled) removePointerListeners?.()
      else if (removePointerListeners) (container as HTMLDivElement & { __removeApproximateLocationListeners?: () => void }).__removeApproximateLocationListeners = removePointerListeners
    }).catch((loadError) => { if (!cancelled) setError(googleMapsErrorMessage(loadError)) })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      dragListener?.remove()
      mapDoubleClickListener?.remove()
      ;(container as HTMLDivElement & { __removeApproximateLocationListeners?: () => void }).__removeApproximateLocationListeners?.()
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
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
    if (internalChangeRef.current) {
      internalChangeRef.current = false
      return
    }
    mapRef.current?.panTo(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="approximate-location-map-shell google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="approximate-location-map google-map-canvas" role="application" aria-label="Google Maps para mover el punto público aproximado. Desplaza el mapa y toca dos veces para colocar el marcador." />
    {error ? <p className="map-inline-error" role="alert">{error}</p> : null}
  </div>
}
