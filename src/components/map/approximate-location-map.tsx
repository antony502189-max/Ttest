import { useEffect, useRef, useState } from 'react'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, TENERIFE_CENTER, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

export function ApproximateLocationMap({ coordinates, onChange }: { coordinates: Coordinates; onChange: (coordinates: Coordinates) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const onChangeRef = useRef(onChange)
  const initialCoordinatesRef = useRef(coordinates)
  const [error, setError] = useState('')

  useEffect(() => { onChangeRef.current = onChange }, [onChange])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let dragListener: google.maps.MapsEventListener | null = null
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
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: true },
      })
      const pin = new marker.PinElement({ background: '#dff34f', borderColor: '#344500', glyphColor: '#344500', scale: 1.15 })
      const publicMarker = new marker.AdvancedMarkerElement({
        map: mapInstance,
        position: initial,
        content: pin,
        gmpDraggable: true,
        title: 'Ubicaci\u00f3n p\u00fablica aproximada',
      })
      dragListener = publicMarker.addListener('dragend', () => {
        const position = publicMarker.position
        if (!position) return
        const point = position instanceof google.maps.LatLng
          ? { lat: position.lat(), lng: position.lng() }
          : { lat: position.lat, lng: position.lng }
        if (isInsideTenerife(point)) onChangeRef.current(point)
      })
      mapRef.current = mapInstance
      markerRef.current = publicMarker
      resizeObserver = new ResizeObserver(() => {
        const center = mapInstance.getCenter()
        google.maps.event.trigger(mapInstance, 'resize')
        if (center) mapInstance.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)
    }).catch((loadError) => { if (!cancelled) setError(googleMapsErrorMessage(loadError)) })
    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      dragListener?.remove()
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
    mapRef.current?.panTo(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="approximate-location-map-shell google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="approximate-location-map google-map-canvas" role="application" aria-label="Google Maps para mover el punto público aproximado" />
    {error ? <p className="map-inline-error" role="alert">{error}</p> : null}
  </div>
}
