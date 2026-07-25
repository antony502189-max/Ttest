import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { importLibrary } from '@googlemaps/js-api-loader'
import { MarkerClusterer, SuperClusterAlgorithm } from '@googlemaps/markerclusterer'
import { Heart, MapPin, X } from 'lucide-react'
import { MediaImage } from '@/components/media-image'
import { AdvancedClusterRenderer, createPriceMarkerContent, priceLabel, setPriceMarkerState } from '@/components/map/map-icons'
import { useApp } from '@/contexts/app-context'
import { getCriticalRestrictions } from '@/lib/listings'
import { filterListings, pointInPolygon } from '@/lib/search'
import { listingMatchesTenerifeLocation, resolveTenerifeLocation } from '@/lib/tenerife'
import { cn } from '@/lib/utils'
import type { Listing, MapPolygonPoint, RentalMode } from '@/types'
import '@/mobile-map-ideal.css'

type MobileMapLanguage = 'es' | 'en' | 'ru'

export type MobileMapBounds = {
  north: number
  south: number
  east: number
  west: number
}

type MobileFilteredListings = {
  ids: Set<string>
  rentalMode: RentalMode | null
  active: boolean
}

const labels = {
  es: { close: 'Cerrar', view: 'Ver anuncio', favorite: 'Guardar', unfavorite: 'Quitar de favoritos', capacity: (count: number) => `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}` },
  en: { close: 'Close', view: 'View listing', favorite: 'Save', unfavorite: 'Remove from favorites', capacity: (count: number) => `Room for ${count} ${count === 1 ? 'person' : 'people'}` },
  ru: { close: 'Закрыть', view: 'Перейти к объявлению', favorite: 'Сохранить', unfavorite: 'Убрать из избранного', capacity: (count: number) => `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}` },
} as const

function isInsideBounds(listing: Listing, bounds?: MobileMapBounds | null) {
  if (!bounds) return true
  const { lat, lng } = listing.coordinates
  const longitudeMatches = bounds.west <= bounds.east
    ? lng >= bounds.west && lng <= bounds.east
    : lng >= bounds.west || lng <= bounds.east
  return lat >= bounds.south && lat <= bounds.north && longitudeMatches
}

export function MobileMapListingsLayer({ mapRef, mapReady, language, drawing, query, polygon, bounds, onVisibleCount }: {
  mapRef: MutableRefObject<google.maps.Map | null>
  mapReady: boolean
  language: MobileMapLanguage
  drawing: boolean
  query: string
  polygon: MapPolygonPoint[]
  bounds?: MobileMapBounds | null
  onVisibleCount?: (count: number) => void
}) {
  const { allListings, discarded, rentalMode, filters, favorites, toggleFavorite } = useApp()
  const [selectedId, setSelectedId] = useState('')
  const [mobileResultFilter, setMobileResultFilter] = useState<MobileFilteredListings | null>(null)
  const markersRef = useRef(new Map<string, google.maps.marker.AdvancedMarkerElement>())
  const markerContentRef = useRef(new Map<string, HTMLElement>())
  const clusterRef = useRef<MarkerClusterer | null>(null)
  const fittedSignatureRef = useRef('')
  const t = labels[language]

  useEffect(() => {
    const receive = (event: Event) => {
      const detail = (event as CustomEvent<{ listingIds?: string[]; rentalMode?: RentalMode | null; active?: boolean }>).detail
      if (!Array.isArray(detail?.listingIds)) return
      setMobileResultFilter({
        ids: new Set(detail.listingIds),
        rentalMode: detail.rentalMode ?? null,
        active: detail.active === true,
      })
    }
    window.addEventListener('112233:mobile-filtered-listings', receive)
    window.dispatchEvent(new Event('112233:request-mobile-filtered-listings'))
    return () => window.removeEventListener('112233:mobile-filtered-listings', receive)
  }, [])

  const items = useMemo(() => {
    const location = resolveTenerifeLocation(query || 'Tenerife')
    const resultFilter = mobileResultFilter?.active && (!mobileResultFilter.rentalMode || mobileResultFilter.rentalMode === rentalMode)
      ? mobileResultFilter.ids
      : null
    return filterListings(allListings.filter((listing) => !discarded.has(listing.id)), rentalMode, filters)
      .filter((listing) => listingMatchesTenerifeLocation(listing, location))
      .filter((listing) => polygon.length < 3 || pointInPolygon(listing.coordinates, polygon))
      .filter((listing) => isInsideBounds(listing, bounds))
      .filter((listing) => !resultFilter || resultFilter.has(listing.id))
  }, [allListings, bounds, discarded, filters, mobileResultFilter, polygon, query, rentalMode])
  const signature = useMemo(() => items.map((item) => `${item.id}:${item.coordinates.lat}:${item.coordinates.lng}:${item.price}`).join('|'), [items])
  const selected = items.find((item) => item.id === selectedId)

  useEffect(() => {
    onVisibleCount?.(items.length)
    const map = mapRef.current
    if (map) {
      map.getDiv().dataset.listingCount = String(items.length)
      map.getDiv().dataset.boundsFiltered = bounds ? 'true' : 'false'
    }
  }, [bounds, items.length, mapRef, onVisibleCount])

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
    if (drawing) setSelectedId('')
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
      markerContentRef.current.clear()
    }

    const createMarkers = async () => {
      await importLibrary('marker')
      if (cancelled || !mapRef.current) return
      clear()

      const markers = items.map((listing) => {
        const content = createPriceMarkerContent(listing)
        content.dataset.testid = `mobile-map-marker-${listing.id}`
        content.dataset.listingId = listing.id
        content.dataset.rentalMode = listing.rentalMode
        content.dataset.price = String(listing.price)
        content.dataset.area = listing.area
        content.dataset.city = listing.city
        content.classList.add('m2-listing-marker')
        setPriceMarkerState(content, false, false)
        const marker = new google.maps.marker.AdvancedMarkerElement({
          position: listing.coordinates,
          content,
          title: `${listing.area}, ${priceLabel(listing)}`,
          gmpClickable: true,
          collisionBehavior: google.maps.CollisionBehavior.REQUIRED,
          zIndex: 10,
        })
        const select = () => {
          setSelectedId(listing.id)
          map.panTo(listing.coordinates)
        }
        marker.addEventListener('gmp-click', select)
        content.addEventListener('click', (event) => { event.stopPropagation(); select() })
        markersRef.current.set(listing.id, marker)
        markerContentRef.current.set(listing.id, content)
        return marker
      })

      clusterRef.current = new MarkerClusterer({
        map,
        markers,
        algorithm: new SuperClusterAlgorithm({ radius: 42, maxZoom: 9 }),
        renderer: new AdvancedClusterRenderer(),
      })

      if (!bounds && polygon.length < 3 && items.length && fittedSignatureRef.current !== signature) {
        fittedSignatureRef.current = signature
        const fitBounds = new google.maps.LatLngBounds()
        items.forEach((listing) => fitBounds.extend(listing.coordinates))
        map.fitBounds(fitBounds, { top: 96, right: 34, bottom: 150, left: 34 })
        google.maps.event.addListenerOnce(map, 'idle', () => {
          const zoom = map.getZoom() ?? 0
          if (zoom > 13) map.setZoom(13)
          if (zoom < 9.5) map.setZoom(9.5)
        })
      }
    }

    void createMarkers()
    const closeOnMap = map.addListener('click', () => {
      if (!drawing) setSelectedId('')
    })
    return () => {
      cancelled = true
      closeOnMap.remove()
      clear()
    }
  }, [bounds, drawing, items, mapReady, mapRef, polygon.length, signature])

  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const active = id === selectedId
      const content = markerContentRef.current.get(id)
      if (content) setPriceMarkerState(content, active, false)
      marker.zIndex = active ? 4000 : 10
    })
  }, [selectedId])

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
  const requirements = Array.from(new Set([...getCriticalRestrictions(selected).slice(0, 2), capacity]))
  const saved = favorites.has(selected.id)
  const openListing = () => {
    window.dispatchEvent(new CustomEvent('112233:open-mobile-listing', { detail: { listingId: selected.id, panel: 'results' } }))
  }

  return <article className="m2-map-listing-preview" data-testid="mobile-map-listing-preview" data-listing-id={selected.id}>
    <button type="button" className="m2-map-listing-preview__media" onClick={openListing} aria-label={t.view}><MediaImage src={selected.images[0]} alt={selected.title} /></button>
    <div className="m2-map-listing-preview__body">
      <button type="button" className="m2-map-listing-preview__close" onClick={() => setSelectedId('')} aria-label={t.close}><X /></button>
      <p><MapPin />{selected.area}, {selected.city}</p>
      <button type="button" className="m2-map-listing-preview__title" onClick={openListing}>{selected.title}</button>
      <strong>{priceLabel(selected)} <small>/{selected.cadence}</small></strong>
      <div className="m2-map-listing-preview__requirements">{requirements.map((requirement) => <span key={requirement}>{requirement}</span>)}</div>
      <div className="m2-map-listing-preview__actions">
        <button type="button" className={cn('m2-map-listing-preview__favorite', saved && 'is-saved')} onClick={() => toggleFavorite(selected.id)} aria-pressed={saved} aria-label={saved ? t.unfavorite : t.favorite}><Heart fill={saved ? 'currentColor' : 'none'} /></button>
        <button type="button" className="m2-map-listing-preview__open" onClick={openListing}>{t.view}</button>
      </div>
    </div>
  </article>
}
