import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowLeft, Camera, Expand, Navigation } from 'lucide-react'
import { useI18n } from '@/contexts/i18n-context'
import { GOOGLE_MAPS_AUTH_FAILURE_EVENT, googleMapsAuthErrorMessage, googleMapsConfig, googleMapsErrorMessage, GoogleMapsSetupError, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS } from '@/lib/tenerife'
import type { Coordinates, Listing } from '@/types'
import '@/listing-location-section.css'

const locationCopy = {
  es: {
    mapAria: 'Mapa de la ubicación aproximada del anuncio',
    markerTitle: 'Ubicación aproximada del anuncio',
    mapUnavailable: 'Mapa no disponible',
    actionsAria: 'Acciones de ubicación',
    directions: 'Calcular ruta',
    streetView: 'Street View',
    heading: 'Ubicación aproximada',
    intro: 'El mapa muestra calles y referencias de la zona sin publicar la dirección exacta.',
    openMapAria: 'Abrir mapa de ubicación a pantalla completa',
    openMap: 'Ver mapa',
    dialogTitle: 'Ubicación',
    closeMap: 'Volver al anuncio',
  },
  en: {
    mapAria: 'Map of the listing’s approximate location',
    markerTitle: 'Approximate listing location',
    mapUnavailable: 'Map unavailable',
    actionsAria: 'Location actions',
    directions: 'Get directions',
    streetView: 'Street View',
    heading: 'Approximate location',
    intro: 'The map shows nearby streets and landmarks without publishing the exact address.',
    openMapAria: 'Open the location map full screen',
    openMap: 'View map',
    dialogTitle: 'Location',
    closeMap: 'Back to listing',
  },
  ru: {
    mapAria: 'Карта примерного местоположения объявления',
    markerTitle: 'Примерное местоположение объявления',
    mapUnavailable: 'Карта недоступна',
    actionsAria: 'Действия с местоположением',
    directions: 'Построить маршрут',
    streetView: 'Street View',
    heading: 'Примерное местоположение',
    intro: 'На карте показаны улицы и ориентиры района без публикации точного адреса.',
    openMapAria: 'Открыть карту местоположения на весь экран',
    openMap: 'Открыть карту',
    dialogTitle: 'Местоположение',
    closeMap: 'Назад к объявлению',
  },
} as const

type ListingLocationMapProps = {
  coordinates: Coordinates
  interactive?: boolean
}

function ListingLocationMap({ coordinates, interactive = false }: ListingLocationMapProps) {
  const { language } = useI18n()
  const t = locationCopy[language]
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
        zoom: interactive ? 18 : 16,
        minZoom: 11,
        maxZoom: 20,
        mapId: googleMapsConfig.mapId,
        mapTypeId: 'roadmap',
        disableDefaultUI: true,
        zoomControl: interactive,
        streetViewControl: interactive,
        mapTypeControl: false,
        fullscreenControl: false,
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
        title: t.markerTitle,
        zIndex: 1000,
      })
      mapRef.current = map
      markerRef.current = locationMarker

      // The preview is born at its final size. Repeated resize events on some
      // Android/WebView combinations can leave a stale Google render layer in
      // the middle of the preview. Only the true fullscreen map needs live
      // resize handling for browser chrome/orientation changes.
      if (interactive) {
        resizeObserver = new ResizeObserver(() => {
          const center = map.getCenter()
          google.maps.event.trigger(map, 'resize')
          if (center) map.setCenter(center)
        })
        resizeObserver.observe(containerRef.current)
      }
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
  }, [interactive, t.markerTitle])

  useEffect(() => {
    if (markerRef.current) markerRef.current.position = coordinates
    mapRef.current?.setCenter(coordinates)
  }, [coordinates.lat, coordinates.lng, coordinates])

  return <div className="listing-location-google-map-shell" data-provider="google-maps">
    <div ref={containerRef} className="listing-location-google-map" role="application" aria-label={t.mapAria} />
    {error ? <div className="map-inline-error listing-location-map-error" role="alert"><strong>{t.mapUnavailable}</strong><span>{error}</span></div> : null}
  </div>
}

export function ListingLocationSection({ listing }: { listing: Listing }) {
  const { language } = useI18n()
  const t = locationCopy[language]
  const [open, setOpen] = useState(false)
  const backButtonRef = useRef<HTMLButtonElement>(null)
  const destination = `${listing.coordinates.lat},${listing.coordinates.lng}`
  const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`
  const streetViewUrl = `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${encodeURIComponent(destination)}`

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    requestAnimationFrame(() => backButtonRef.current?.focus({ preventScroll: true }))
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const actions = <div className="listing-location-actions" aria-label={t.actionsAria}>
    <a href={directionsUrl} target="_blank" rel="noopener noreferrer"><Navigation aria-hidden="true" />{t.directions}</a>
    <a href={streetViewUrl} target="_blank" rel="noopener noreferrer"><Camera aria-hidden="true" />{t.streetView}</a>
  </div>

  const fullscreenMap = open ? createPortal(
    <div className="listing-location-dialog" role="dialog" aria-modal="true" aria-label={t.dialogTitle}>
      <div className="listing-location-dialog__map"><ListingLocationMap coordinates={listing.coordinates} interactive /></div>
      <button ref={backButtonRef} type="button" className="listing-location-dialog__back" onClick={() => setOpen(false)} aria-label={t.closeMap}>
        <ArrowLeft aria-hidden="true" />
      </button>
      <h2 className="sr-only">{t.dialogTitle}</h2>
    </div>,
    document.body,
  ) : null

  return <>
    <section className="listing-section listing-location-section">
      <h2>{t.heading}</h2>
      <p className="map-intro">{t.intro}</p>
      {actions}
      <div className="listing-location-preview">
        <div className="listing-location-preview__map" aria-hidden="true"><ListingLocationMap coordinates={listing.coordinates} /></div>
        <button type="button" className="listing-location-preview__open" onClick={() => setOpen(true)} aria-label={t.openMapAria}>
          <Expand aria-hidden="true" /><span>{t.openMap}</span>
        </button>
      </div>
    </section>
    {fullscreenMap}
  </>
}
