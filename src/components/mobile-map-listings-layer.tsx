import { useEffect, useMemo, useRef, useState, type MutableRefObject } from 'react'
import { MarkerClusterer, SuperClusterAlgorithm } from '@googlemaps/markerclusterer'
import { ChevronLeft, ChevronRight, Heart, MapPin, X } from 'lucide-react'
import { MediaImage } from '@/components/media-image'
import { AdvancedClusterRenderer, createPriceMarkerContent, priceLabel, setClusterPromotionState, setPriceMarkerState } from '@/components/map/map-icons'
import { useApp } from '@/contexts/app-context'
import { translateText } from '@/contexts/i18n-context'
import { cn } from '@/lib/utils'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { buildDisplayMarkerPositions, coincidentListingIdsFor, exactCoincidentListingIds } from '@/lib/map-marker-overlap'
import { hasListingCoordinates } from '@/lib/listings'
import type { Listing } from '@/types'
import '@/mobile-map-ideal.css'

type MobileMapLanguage = 'es' | 'en' | 'ru'

const labels = {
  es: { close: 'Cerrar', view: 'Ver anuncio', favorite: 'Guardar', unfavorite: 'Quitar de favoritos', capacity: (count: number) => `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}`, group: (count: number) => `${count} anuncios en esta dirección` },
  en: { close: 'Close', view: 'View listing', favorite: 'Save', unfavorite: 'Remove from favorites', capacity: (count: number) => `Room for ${count} ${count === 1 ? 'person' : 'people'}`, group: (count: number) => `${count} listings at this address` },
  ru: { close: 'Закрыть', view: 'Перейти к объявлению', favorite: 'Сохранить', unfavorite: 'Убрать из избранного', capacity: (count: number) => `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}`, group: (count: number) => `${count} объявления по этому адресу` },
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
  const [coincidentIds, setCoincidentIds] = useState<string[]>([])
  const markersRef = useRef(new Map<string, google.maps.marker.AdvancedMarkerElement>())
  const clusterRef = useRef<MarkerClusterer | null>(null)
  const fittedSignatureRef = useRef('')
  const t = labels[language]
  const mappedItems = useMemo(() => items.filter(hasListingCoordinates), [items])
  // Keep camera-fitting tied to actual marker geometry rather than TOP state.
  const signature = useMemo(() => mappedItems.map((item) => `${item.id}:${item.coordinates.lat}:${item.coordinates.lng}:${item.price}`).join('|'), [mappedItems])
  const promotionSignature = useMemo(() => mappedItems.map((item) => `${item.id}:${item.promoted ? 'top' : 'normal'}`).join('|'), [mappedItems])
  const selected = mappedItems.find((item) => item.id === selectedId)
  const coincidentListings = coincidentIds.flatMap((id) => {
    const listing = mappedItems.find((item) => item.id === id)
    return listing ? [listing] : []
  })

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
      await loadGoogleMaps()
      if (cancelled || !mapRef.current) return
      clear()
      const displayPositions = buildDisplayMarkerPositions(mappedItems)

      const markers = mappedItems.map((listing) => {
        const content = createPriceMarkerContent(listing)
        content.dataset.testid = `mobile-map-marker-${listing.id}`
        content.dataset.listingId = listing.id
        content.classList.add('m2-listing-marker')
        content.dataset.markerZIndex = listing.promoted ? '100' : '10'
        const display = displayPositions.get(listing.id) ?? { position: listing.coordinates, coincidentCount: 1 }
        content.dataset.coincidentCount = String(display.coincidentCount)
        content.dataset.displayPosition = `${display.position.lat.toFixed(7)},${display.position.lng.toFixed(7)}`
        const marker = new google.maps.marker.AdvancedMarkerElement({
          position: display.position,
          content,
          title: `${listing.approximateAddress ? `${listing.approximateAddress}, ${listing.city}` : `${listing.area}, ${listing.city}`}, ${priceLabel(listing)}`,
          gmpClickable: true,
          collisionBehavior: google.maps.CollisionBehavior.OPTIONAL_AND_HIDES_LOWER_PRIORITY,
          zIndex: listing.promoted ? 100 : 10,
        })
        const select = () => {
          const groupIds = coincidentListingIdsFor(mappedItems, listing.id)
          setCoincidentIds(groupIds.length > 1 ? groupIds : [])
          setSelectedId(listing.id)
          marker.zIndex = 4000
          map.panTo(display.position)
        }
        marker.addEventListener('gmp-click', select)
        content.addEventListener('click', (event) => { event.stopPropagation(); select() })
        markersRef.current.set(listing.id, marker)
        return marker
      })

      if (googleMapsTestSdkEnabled) markers.forEach((marker) => { marker.map = map })
      else {
        clusterRef.current = new MarkerClusterer({
          map,
          markers,
          algorithm: new SuperClusterAlgorithm({ radius: 54, maxZoom: 20 }),
          renderer: new AdvancedClusterRenderer(),
          onClusterClick: (_event, cluster, clusterMap) => {
            const clusteredIds = cluster.markers.flatMap((clusterMarker) => {
              if (!(clusterMarker instanceof google.maps.marker.AdvancedMarkerElement)) return []
              const markerContent = clusterMarker.content
              const listingId = markerContent instanceof HTMLElement ? markerContent.dataset.listingId : undefined
              return listingId ? [listingId] : []
            })
            const coincidentIds = exactCoincidentListingIds(mappedItems, clusteredIds)
            if (coincidentIds.length > 1) {
              setCoincidentIds(coincidentIds)
              setSelectedId(coincidentIds[0])
              const first = mappedItems.find((listing) => listing.id === coincidentIds[0])
              if (first) clusterMap.panTo(first.coordinates)
              return
            }
            setCoincidentIds([])
            if (cluster.bounds) clusterMap.fitBounds(cluster.bounds)
          },
        })
      }

      if (mappedItems.length && fittedSignatureRef.current !== signature) {
        fittedSignatureRef.current = signature
        const bounds = new google.maps.LatLngBounds()
        mappedItems.forEach((listing) => bounds.extend(listing.coordinates))
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
  }, [mappedItems, mapReady, mapRef, signature])

  useEffect(() => {
    if (!selectedId || mappedItems.some((item) => item.id === selectedId)) return
    setSelectedId('')
  }, [mappedItems, selectedId])

  useEffect(() => {
    if (!selectedId) {
      setCoincidentIds((current) => current.length ? [] : current)
      return
    }
    const next = coincidentListingIdsFor(mappedItems, selectedId)
    const nextIds = next.length > 1 ? next : []
    setCoincidentIds((current) => current.join('|') === nextIds.join('|') ? current : nextIds)
  }, [mappedItems, selectedId])

  useEffect(() => {
    if (drawing) setCoincidentIds([])
  }, [drawing])

  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const listing = mappedItems.find((item) => item.id === id)
      if (!listing || !(marker.content instanceof HTMLElement)) return
      const selectedMarker = id === selectedId
      setPriceMarkerState(marker.content, selectedMarker, false, Boolean(listing.promoted))
      marker.zIndex = selectedMarker ? 4000 : listing.promoted ? 100 : 10
      marker.content.dataset.markerZIndex = String(marker.zIndex)
    })
    const clusterer = clusterRef.current
    if (!clusterer) return
    const clusters = (clusterer as unknown as { clusters: Array<{ marker?: google.maps.Marker | google.maps.marker.AdvancedMarkerElement; markers: Array<google.maps.Marker | google.maps.marker.AdvancedMarkerElement> }> }).clusters
    clusters.forEach((candidate) => {
      if (!(candidate.marker instanceof google.maps.marker.AdvancedMarkerElement)) return
      const clusterContent = candidate.marker.content
      if (!(clusterContent instanceof HTMLElement)) return
      const clusterPromoted = candidate.markers.some((child) => {
        if (!(child instanceof google.maps.marker.AdvancedMarkerElement)) return false
        const childContent = child.content
        return childContent instanceof HTMLElement && Boolean(childContent.querySelector('.map-price-marker.is-promoted'))
      })
      setClusterPromotionState(clusterContent, clusterPromoted)
      candidate.marker.zIndex = (clusterPromoted ? 2000 : 1000) + candidate.markers.length
    })
  }, [mappedItems, promotionSignature, selectedId])

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
  const capacity = selected.roomCapacity == null ? translateText('Consultar con el anunciante', language) : t.capacity(selected.roomCapacity)
  const requirements = Array.from(new Set([...selected.restrictions.slice(0, 2).map((restriction) => translateText(restriction, language)), capacity]))
  const cadence = selected.cadence === 'noche' ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche' : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'
  const saved = favorites.has(selected.id)
  const externalUrl = selected.isExternal && selected.sourceUrl ? selected.sourceUrl : null
  const openInternalListing = () => {
    window.dispatchEvent(new CustomEvent('112233:open-mobile-listing', { detail: { listingId: selected.id } }))
  }
  const translatedTitle = translateText(selected.title, language)
  const carousel = coincidentListings.length > 1 ? coincidentListings : [selected]
  const carouselIndex = Math.max(0, carousel.findIndex((listing) => listing.id === selected.id))
  const previous = carouselIndex > 0 ? carousel[carouselIndex - 1] : null
  const next = carouselIndex < carousel.length - 1 ? carousel[carouselIndex + 1] : null
  const selectSibling = (id: string) => {
    setSelectedId(id)
    const listing = mappedItems.find((item) => item.id === id)
    if (listing) mapRef.current?.panTo(listing.coordinates)
  }

  return <article
    className="m2-map-listing-preview"
    data-testid="mobile-map-listing-preview"
    data-listing-id={selected.id}
    data-group-size={carousel.length}
    data-promoted={selected.promoted || undefined}
  >
    <div className="m2-map-listing-preview__media-shell">
      {externalUrl
        ? <a className="m2-map-listing-preview__media" href={externalUrl} target="_blank" rel="noopener noreferrer" aria-label={`${t.view}: ${translatedTitle}`}><MediaImage src={selected.images[0]} alt={selected.title} /></a>
        : <button type="button" className="m2-map-listing-preview__media" onClick={openInternalListing} aria-label={`${t.view}: ${translatedTitle}`}><MediaImage src={selected.images[0]} alt={selected.title} /></button>}
      {carousel.length > 1 ? <>
        <button type="button" className="m2-map-listing-preview__carousel-arrow m2-map-listing-preview__carousel-arrow--prev" aria-label={language === 'ru' ? 'Предыдущее объявление по этому адресу' : language === 'en' ? 'Previous listing at this address' : 'Anuncio anterior en esta dirección'} disabled={!previous} onClick={() => previous && selectSibling(previous.id)}><ChevronLeft /></button>
        <button type="button" className="m2-map-listing-preview__carousel-arrow m2-map-listing-preview__carousel-arrow--next" aria-label={language === 'ru' ? 'Следующее объявление по этому адресу' : language === 'en' ? 'Next listing at this address' : 'Siguiente anuncio en esta dirección'} disabled={!next} onClick={() => next && selectSibling(next.id)}><ChevronRight /></button>
        <span className="m2-map-listing-preview__carousel-count" aria-label={`${carouselIndex + 1} / ${carousel.length}`}>${carouselIndex + 1}/${carousel.length}</span>
      </> : null}
      {selected.promoted ? <span className="m2-map-listing-preview__promoted" aria-label="TOP">👍</span> : null}
    </div>
    <div className="m2-map-listing-preview__body">
      <button type="button" className="m2-map-listing-preview__close" onClick={() => { setSelectedId(''); setCoincidentIds([]) }} aria-label={t.close}><X /></button>
      <p><MapPin />{selected.approximateAddress ? `${selected.approximateAddress}, ${selected.city}` : `${selected.area}, ${selected.city}`}</p>
      <h2>{translatedTitle}</h2>
      <strong>{priceLabel(selected)} {selected.sourcePriceText ? null : <small>/{cadence}</small>}</strong>
      <div className="m2-map-listing-preview__requirements">{requirements.map((requirement) => <span key={requirement}>{requirement}</span>)}</div>
      <div className="m2-map-listing-preview__actions">
        <button type="button" className={cn('m2-map-listing-preview__favorite', saved && 'is-saved')} onClick={() => toggleFavorite(selected.id)} aria-pressed={saved} aria-label={saved ? t.unfavorite : t.favorite}><Heart fill={saved ? 'currentColor' : 'none'} /></button>
        {externalUrl
          ? <a className="m2-map-listing-preview__open" href={externalUrl} target="_blank" rel="noopener noreferrer">{t.view}</a>
          : <button type="button" className="m2-map-listing-preview__open" onClick={openInternalListing}>{t.view}</button>}
      </div>
    </div>
  </article>
}
