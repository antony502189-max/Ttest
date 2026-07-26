import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { importLibrary } from '@googlemaps/js-api-loader'
import { MarkerClusterer, SuperClusterAlgorithm } from '@googlemaps/markerclusterer'
import { Heart, MapPin, X } from 'lucide-react'
import { MediaImage } from '@/components/media-image'
import { AdvancedClusterRenderer, createPriceMarkerContent, priceLabel } from '@/components/map/map-icons'
import { useApp } from '@/contexts/app-context'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'
import '@/mobile-map-ideal.css'

type MobileMapLanguage = 'es' | 'en' | 'ru'

const labels = {
  es: { close: 'Cerrar', view: 'Ver anuncio', favorite: 'Guardar', unfavorite: 'Quitar de favoritos', capacity: (count: number) => `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}` },
  en: { close: 'Close', view: 'View listing', favorite: 'Save', unfavorite: 'Remove from favorites', capacity: (count: number) => `Room for ${count} ${count === 1 ? 'person' : 'people'}` },
  ru: { close: 'Закрыть', view: 'Перейти к объявлению', favorite: 'Сохранить', unfavorite: 'Убрать из избранного', capacity: (count: number) => `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}` },
} as const

export function MobileMapListingsLayer({ mapRef, mapReady, language, drawing, items }: {
  mapRef: MutableRefObject<google.maps.Map | null>
  mapReady: boolean
  language: MobileMapLanguage
  drawing: boolean
  items: Listing[]
}) {
  const { favorites, toggleFavorite } = useApp()
  const [selectedId, setSelectedId] = useState('')
  const markersRef = useRef(new Map<string, google.maps.marker.AdvancedMarkerElement>())
  const clusterRef = useRef<MarkerClusterer | null>(null)
  const fittedSignatureRef = useRef('')
  const t = labels[language]
  const signature = useMemo(() => items.map((item) => `${item.id}:${item.coordinates.lat}:${item.coordinates.lng}:${item.price}`).join('|'), [items])
  const selected = items.find((item) => item.id === selectedId)

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const div = map.getDiv()
    div.dataset.mapInteraction = drawing ? 'drawing' : 'interactive'
    div.dataset.gestureHandling = drawing ? 'none' : 'greedy'
    map.setOptions(drawing ? {
      gestureHandling: 'none',
      draggable: false,
      scrollwheel: false,
      disableDoubleClickZoom: true,
      keyboardShortcuts: false,
    } : {
      gestureHandling: 'greedy',
      draggable: true,
      scrollwheel: true,
      disableDoubleClickZoom: false,
      keyboardShortcuts: true,
    })
  }, [drawing, mapReady, mapRef])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    let cancelled = false

    const clear = () => {
      clusterRef.current?.clearMarkers()
      clusterRef.current?.setMap(null)
      clusterRef.current = null
      markersRef.current.forEach((marker) => {
        google.maps.event.clearInstanceListeners(marker)
        marker.map = null
      })
      markersRef.current.clear()
    }

    const createMarkers = async () => {
      await importLibrary('marker')
      if (cancelled || !mapRef.current) return
      clear()

      const markers = items.map((listing) => {
        const content = createPriceMarkerContent(listing)
        content.dataset.testid = `mobile-map-marker-${listing.id}`
        content.dataset.listingId = listing.id
        content.classList.add('m2-listing-marker')
        const marker = new google.maps.marker.AdvancedMarkerElement({
          position: listing.coordinates,
          content,
          title: `${listing.area}, ${priceLabel(listing)}`,
          gmpClickable: true,
          collisionBehavior: google.maps.CollisionBehavior.OPTIONAL_AND_HIDES_LOWER_PRIORITY,
          zIndex: 10,
        })
        const select = () => {
          setSelectedId(listing.id)
          marker.zIndex = 4000
          map.panTo(listing.coordinates)
        }
        marker.addEventListener('gmp-click', select)
        content.addEventListener('click', (event) => { event.stopPropagation(); select() })
        markersRef.current.set(listing.id, marker)
        return marker
      })

      clusterRef.current = new MarkerClusterer({
        map,
        markers,
        algorithm: new SuperClusterAlgorithm({ radius: 54, maxZoom: 15 }),
        renderer: new AdvancedClusterRenderer(),
      })

      if (items.length && fittedSignatureRef.current !== signature) {
        fittedSignatureRef.current = signature
        const bounds = new google.maps.LatLngBounds()
        items.forEach((listing) => bounds.extend(listing.coordinates))
        map.fitBounds(bounds, { top: 96, right: 34, bottom: 150, left: 34 })
        google.maps.event.addListenerOnce(map, 'idle', () => {
          const zoom = map.getZoom() ?? 0
          if (zoom > 13) map.setZoom(13)
          if (zoom < 9.5) map.setZoom(9.5)
          const center = map.getCenter()
          if (center) map.getDiv().dataset.mapCenter = `${center.lat().toFixed(6)},${center.lng().toFixed(6)}`
          map.getDiv().dataset.mapZoom = String(map.getZoom() ?? '')
        })
      }
    }

    void createMarkers()
    return () => { cancelled = true; clear() }
  }, [items, mapReady, mapRef, signature])

  useEffect(() => {
    if (!selectedId || items.some((item) => item.id === selectedId)) return
    setSelectedId('')
  }, [items, selectedId])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const listener = map.addListener('idle', () => {
      const center = map.getCenter()
      if (center) map.getDiv().dataset.mapCenter = `${center.lat().toFixed(6)},${center.lng().toFixed(6)}`
      map.getDiv().dataset.mapZoom = String(map.getZoom() ?? '')
    })
    return () => listener.remove()
  }, [mapReady, mapRef])

  if (!selected) return null
  const capacity = t.capacity(selected.roomCapacity)
  const requirements = Array.from(new Set([...selected.restrictions.slice(0, 2), capacity]))
  const saved = favorites.has(selected.id)
  const openListing = () => {
    window.dispatchEvent(new CustomEvent('112233:open-mobile-listing', { detail: { listingId: selected.id } }))
  }

  return <article className="m2-map-listing-preview" data-testid="mobile-map-listing-preview" data-listing-id={selected.id}>
    <div className="m2-map-listing-preview__media"><MediaImage src={selected.images[0]} alt={selected.title} /></div>
    <div className="m2-map-listing-preview__body">
      <button type="button" className="m2-map-listing-preview__close" onClick={() => setSelectedId('')} aria-label={t.close}><X /></button>
      <p><MapPin />{selected.area}, {selected.city}</p>
      <h2>{selected.title}</h2>
      <strong>{priceLabel(selected)} <small>/{selected.cadence}</small></strong>
      <div className="m2-map-listing-preview__requirements">{requirements.map((requirement) => <span key={requirement}>{requirement}</span>)}</div>
      <div className="m2-map-listing-preview__actions">
        <button type="button" className={cn('m2-map-listing-preview__favorite', saved && 'is-saved')} onClick={() => toggleFavorite(selected.id)} aria-pressed={saved} aria-label={saved ? t.unfavorite : t.favorite}><Heart fill={saved ? 'currentColor' : 'none'} /></button>
        <button type="button" className="m2-map-listing-preview__open" onClick={openListing}>{t.view}</button>
      </div>
    </div>
  </article>
}
