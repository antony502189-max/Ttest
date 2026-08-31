import { useEffect, useRef, useState } from 'react'
import { Expand, Navigation, StreetView } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS } from '@/lib/tenerife'
import type { Coordinates, Listing } from '@/types'
import '@/listing-location-section.css'

type ListingLocationMapProps = {
  coordinates: Coordinates
  interactive?: boolean
}

function ListingLocationMap({ coordinates, interactive = false }: ListingLocationMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<google.maps.Map | null>(null)
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    const handleAuthFailure = () => setError(googleMapsAuthErrorMessage)
    window.addEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)

    loadGoogleMaps().then(({ maps, marker }) => {
      if (cancelled || !containerRef.current) return
      if (!googleMapsConfig.mapId) throw new GoogleMapsSetupError('missing-map-id')
      const map = new maps.Map(containerRef.current, {
        center: coordinates,
        zoom: interactive ? 16 : 15,
        minZoom: 9,
        maxZoom: 20,
        mapId: googleMapsConfig.mapId,
        mapTypeId: 'roadmap',
        disableDefaultUI: true,
        zoomControl: interactive,
        clickableIcons: false,
        keyboardShortcuts: interactive,
        gestureHandling: interactive ? 'greedy' : 'none',
        restriction: { latLngBounds: TENERIFE_BOUNDS, strictBounds: false },
      })
      const pin = new marker.PinElement({ background: '#2f67c7', borderColor: '#ffffff', glyphColor: '#ffffff', scale: 1.05 })
      const locationMarker = new marker.AdvancedMarkerElement({
        map,
        position: coordinates,
        content: pin,
        title: 'Ubicación aproximada del anuncio',
        zIndex: 1000,
      })
      mapRef.current = map
      markerRef.current = locationMarker
      resizeObserver = new ResizeObserver(() => {
        const center = map.getCenter()
        google.maps.event.trigger(map, 'resize')
        if (center) map.setCenter(center)
      })
      resizeObserver.observe(containerRef.current)
      setError('')
    }).catch((loadError) => {
      if (!cancelled) setError(googleMapsErrorMessage(loadError))
    })

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      window.removeEventListener(GOOGLE_MAPS_AUTH_FAILURE_EVENT, handleAuthFailure)
      if (markerRef.current) markerRef.current.map = null
      if (mapRef.current) google.maps.event.clearInstanceListeners(mapRef.current)
      mapRef.current = null
      markerRef.current = null
      container.replaceChildren()
    }
  }, [interactive])

  useEffect(() => {
    if (markerRef.current) markerRef.current.position = coordinates
    mapRef.current?.setCenter(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="listing-location-google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="listing-location-google-map" role="application" aria-label="Mapa de la ubicación aproximada del anuncio" />
    {error ? <div className="map-inline-error listing-location-map-error" role="alert"><strong>Mapa no disponible</strong><span>{error}</span></div> : null}
  </div>
}

export function ListingLocationSection({ listing }: { listing: Listing }) {
  const [open, setOpen] = useState(false)
  const destination = `${listing.coordinates.lat},${listing.coordinates.lng}`
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`
  const streetViewUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${encodeURIComponent(destination)}`

  const actions = <div className="listing-location-actions" aria-label="Acciones de ubicación">
    <a href={directionsUrl} target="_blank" rel="noopener noreferrer"><Navigation aria-hidden="true" />Calcular ruta</a>
    <a href={streetViewUrl} target="_blank" rel="noopener noreferrer"><StreetView aria-hidden="true" />Street View</a>
  </div>

  return <>
    <section className="listing-section listing-location-section">
      <h2>Ubicación aproximada</h2>
      <p className="map-intro">El mapa muestra calles y referencias de la zona sin publicar la dirección exacta.</p>
      {actions}
      <div className="listing-location-preview">
        <div className="listing-location-preview__map" aria-hidden="true"><ListingLocationMap coordinates={listing.coordinates} /></div>
        <button type="button" className="listing-location-preview__open" onClick={() => setOpen(true)} aria-label="Abrir mapa de ubicación a pantalla completa">
          <span><Expand aria-hidden="true" />Ver mapa</span>
        </button>
      </div>
    </section>

    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="listing-location-dialog">
        <DialogHeader className="listing-location-dialog__header">
          <DialogTitle>Ubicación</DialogTitle>
          <DialogDescription>Consulta las calles de la zona, amplía el mapa o abre la ruta y Street View.</DialogDescription>
        </DialogHeader>
        <div className="listing-location-dialog__actions">{actions}</div>
        <div className="listing-location-dialog__map"><ListingLocationMap coordinates={listing.coordinates} interactive /></div>
      </DialogContent>
    </Dialog>
  </>
}
