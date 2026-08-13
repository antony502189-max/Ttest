import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router'
import {
  ArrowDownUp,
  ChevronLeft,
  ChevronRight,
  Heart,
  Image as ImageIcon,
  Map,
  MapPin,
  MessageCircle,
  Phone,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react'
import { MediaImage } from '@/components/media-image'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { defaultFilters } from '@/data/listings'
import { getBedroomCount } from '@/lib/listings'
import { selectMobileSearchListings } from '@/lib/mobile-search'
import { filtersFromParams, filtersToParams } from '@/lib/search'
import type { Listing, RentalMode } from '@/types'
import { cn } from '@/lib/utils'
import '@/mobile-search-results.css'

type ResultsLanguage = Language
type ResultsPanel = 'results' | 'filters' | 'sort'
type ExactRoomCount = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10
type RoomCountFilter = ExactRoomCount | '10+'
const roomCountOptions: readonly RoomCountFilter[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, '10+']
type ResultsOrder = 'relevance' | 'cheap' | 'expensive' | 'saved-new' | 'saved-old' | 'reduced' | 'sqm-cheap' | 'sqm-expensive' | 'area-large' | 'area-small' | 'floor-high' | 'floor-low'
const MOBILE_VIEWPORT = '(max-width: 767px), (max-height: 480px) and (max-width: 900px)'
type ResultsFilters = {
  rentalMode: RentalMode | null
  minPrice: number
  maxPrice: number
  minArea: number
  maxArea: number
  roomTypes: Listing['roomType'][]
  roomCounts: RoomCountFilter[]
}

const createDefaultFilters = (rentalMode: RentalMode | null = null): ResultsFilters => ({
  rentalMode,
  minPrice: 0,
  maxPrice: 1500,
  minArea: 0,
  maxArea: 50,
  roomTypes: [],
  roomCounts: [],
})

const orderKeys: ResultsOrder[] = ['relevance', 'cheap', 'expensive', 'saved-new', 'saved-old', 'reduced', 'sqm-cheap', 'sqm-expensive', 'area-large', 'area-small', 'floor-high', 'floor-low']

const resultsCopy = {
  es: {
    header: (count: number) => `${count} viviendas en Tenerife`, zone: 'Tu zona seleccionada', filters: 'Filtros', order: 'Orden', map: 'Mapa', showing: (count: number, total: number) => `Viendo ${count} de ${total} viviendas`, top: 'Destacado',
    contact: 'Contactar', call: 'Llamar', favorite: 'Guardar en favoritos', unfavorite: 'Quitar de favoritos', discard: 'Ocultar anuncio', photo: 'Siguiente foto', back: 'Volver', close: 'Cerrar', clear: 'Limpiar', empty: 'No hay anuncios que coincidan con estos filtros.',
    vivienda: 'Vivienda', turismo: 'Turismo', price: 'Precio', area: 'Superficie', min: 'Mín', max: 'Máx', housingType: 'Tipo de vivienda', rooms: 'Número de habitaciones', roomCount: (count: number) => `${count} ${count === 1 ? 'habitación' : 'habitaciones'}`, moreThanTenRooms: 'Más de 10 habitaciones',
    individual: 'Habitaciones individuales', shared: 'Habitaciones compartidas', studio: 'Estudios', showListings: 'Ver anuncios', residents: 'residentes',
    relevance: 'Relevancia', cheap: 'Más baratos', expensive: 'Más caros', savedNew: 'Guardados recientemente', savedOld: 'Guardados anteriormente', reduced: 'Precio rebajado', sqmCheap: 'Menor precio por m²', sqmExpensive: 'Mayor precio por m²', areaLarge: 'Mayor superficie', areaSmall: 'Menor superficie', floorHigh: 'Plantas altas', floorLow: 'Plantas bajas',
  },
  en: {
    header: (count: number) => `${count} properties in Tenerife`, zone: 'Your selected area', filters: 'Filters', order: 'Order', map: 'Map', showing: (count: number, total: number) => `Viewing ${count} of ${total} properties`, top: 'Featured',
    contact: 'Contact', call: 'Call', favorite: 'Add to favorites', unfavorite: 'Remove from favorites', discard: 'Hide listing', photo: 'Next photo', back: 'Back', close: 'Close', clear: 'Clear', empty: 'No listings match these filters.',
    vivienda: 'Housing', turismo: 'Tourism', price: 'Price', area: 'Area', min: 'Min', max: 'Max', housingType: 'Property category', rooms: 'Number of rooms', roomCount: (count: number) => `${count} ${count === 1 ? 'room' : 'rooms'}`, moreThanTenRooms: 'More than 10 rooms',
    individual: 'Individual rooms', shared: 'Shared rooms', studio: 'Studios', showListings: 'View listings', residents: 'residents',
    relevance: 'Relevance', cheap: 'Cheapest', expensive: 'Most expensive', savedNew: 'Saved recently', savedOld: 'Saved earlier', reduced: 'Reduced price', sqmCheap: 'Lowest price per m²', sqmExpensive: 'Highest price per m²', areaLarge: 'Largest area', areaSmall: 'Smallest area', floorHigh: 'Upper floors', floorLow: 'Lower floors',
  },
  ru: {
    header: (count: number) => `${count} объявлений на Тенерифе`, zone: 'Ваша выделенная зона', filters: 'Фильтры', order: 'Порядок', map: 'Карта', showing: (count: number, total: number) => `Просмотр ${count} из ${total} объявлений`, top: 'Топ',
    contact: 'Связаться', call: 'Позвонить', favorite: 'Добавить в избранное', unfavorite: 'Убрать из избранного', discard: 'Скрыть объявление', photo: 'Следующая фотография', back: 'Назад', close: 'Закрыть', clear: 'Сбросить', empty: 'Нет объявлений, подходящих под выбранные фильтры.',
    vivienda: 'Жильё', turismo: 'Туризм', price: 'Цена', area: 'Площадь', min: 'Мин', max: 'Макс', housingType: 'Тип жилья', rooms: 'Количество комнат', roomCount: (count: number) => `${count} ${count === 1 ? 'комната' : count >= 2 && count <= 4 ? 'комнаты' : 'комнат'}`, moreThanTenRooms: 'Больше 10 комнат',
    individual: 'Отдельные комнаты', shared: 'Общие комнаты', studio: 'Студии', showListings: 'Перейти к объявлениям', residents: 'жильцов',
    relevance: 'Релевантность', cheap: 'Дешевые', expensive: 'Дорогие', savedNew: 'Сохраненные недавно', savedOld: 'Сохраненные раньше', reduced: 'Со сниженной ценой', sqmCheap: 'Дешевые евро/м²', sqmExpensive: 'Дорогие евро/м²', areaLarge: 'С большей площадью', areaSmall: 'С меньшей площадью', floorHigh: 'Верхние этажи', floorLow: 'Нижние этажи',
  },
} as const

type ResultsCopy = typeof resultsCopy.es

const fallbackImage = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23282828"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%235d655f"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23727b74"/%3E%3C/svg%3E'

function imageFallback(event: SyntheticEvent<HTMLImageElement>) {
  event.currentTarget.src = fallbackImage
}

function formatPrice(listing: Listing, language: ResultsLanguage) {
  const value = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES').format(listing.price)
  const cadence = listing.cadence === 'noche' ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche' : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'
  return `${value} € / ${cadence}`
}

function capacityLabel(language: ResultsLanguage, count: number | null) {
  if (count == null) return 'Consultar con el anunciante'
  if (language === 'ru') return `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}`
  if (language === 'en') return `Room for ${count} ${count === 1 ? 'person' : 'people'}`
  return `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}`
}

function bedroomFact(language: ResultsLanguage, count: number) {
  if (language === 'ru') return `${count} ${count === 1 ? 'комната' : count >= 2 && count <= 4 ? 'комнаты' : 'комнат'}`
  if (language === 'en') return `${count} ${count === 1 ? 'room' : 'rooms'}`
  return `${count} ${count === 1 ? 'habitación' : 'habitaciones'}`
}

function toggleValue<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
}

function stableFloor(listing: Listing) {
  return [...listing.id].reduce((value, character) => (value * 31 + character.charCodeAt(0)) % 11, 0)
}

function orderLabel(copy: ResultsCopy, order: ResultsOrder) {
  const labels: Record<ResultsOrder, string> = {
    relevance: copy.relevance, cheap: copy.cheap, expensive: copy.expensive, 'saved-new': copy.savedNew, 'saved-old': copy.savedOld,
    reduced: copy.reduced, 'sqm-cheap': copy.sqmCheap, 'sqm-expensive': copy.sqmExpensive, 'area-large': copy.areaLarge,
    'area-small': copy.areaSmall, 'floor-high': copy.floorHigh, 'floor-low': copy.floorLow,
  }
  return labels[order]
}

function MobileResultCard({ listing, index, language, favorite, onFavorite, onDiscard, onContact, onOpen }: {
  listing: Listing; index: number; language: ResultsLanguage; favorite: boolean; onFavorite: () => void; onDiscard: () => void; onContact: () => void; onOpen: () => void
}) {
  const t = resultsCopy[language] as ResultsCopy
  const [imageIndex, setImageIndex] = useState(0)
  const images = listing.images.length ? listing.images : [fallbackImage]
  const nextImage = () => setImageIndex((current) => (current + 1) % images.length)
  return <article className="m2-result-card" data-listing-id={listing.id}>
    <div className="m2-result-card__media"><button type="button" className="m2-result-card__image-button" onClick={onOpen} aria-label={listing.title}><MediaImage src={images[imageIndex]} onError={imageFallback} alt={`${listing.title}, ${imageIndex + 1}/${images.length}`} loading="lazy" /></button>{index < 2 ? <span className="m2-result-card__top">{t.top}</span> : null}<span className="m2-result-card__counter"><ImageIcon />{imageIndex + 1}/{images.length}</span>{images.length > 1 ? <button type="button" className="m2-result-card__next" onClick={nextImage} aria-label={t.photo}><ChevronRight /></button> : null}</div>
    <div className="m2-result-card__content"><p className="m2-result-card__location"><MapPin />{listing.area}, {listing.city}</p><h2>{listing.title}</h2><strong className="m2-result-card__price">{formatPrice(listing, language)}</strong><p className="m2-result-card__facts">{listing.roomType} · {bedroomFact(language, getBedroomCount(listing))} · {listing.roomSizeM2 == null ? 'Consultar con el anunciante' : `${listing.roomSizeM2} m²`} · {listing.currentResidents} {t.residents}</p><p className="m2-result-card__availability">{listing.available}</p><div className="m2-result-card__badges">{Array.from(new Set([...listing.restrictions.slice(0, 2), capacityLabel(language, listing.roomCapacity)])).map((restriction) => <span key={restriction}>{restriction}</span>)}</div>
      <div className="m2-result-card__actions"><button type="button" onClick={onContact}><MessageCircle />{t.contact}</button>{listing.showPhone && listing.contactPhone ? <a href={`tel:${listing.contactPhone}`}><Phone />{t.call}</a> : null}<button type="button" className="m2-result-card__discard" onClick={onDiscard} aria-label={t.discard}><Trash2 /></button><button type="button" className={cn('m2-result-card__favorite', favorite && 'is-active')} onClick={onFavorite} aria-label={favorite ? t.unfavorite : t.favorite} aria-pressed={favorite}><Heart /></button></div>
    </div>
  </article>
}

export function MobileSearchResults() {
  const { allListings, discarded, discardListing, favorites, toggleFavorite, currentUser, rentalMode, setRentalMode, filters: appFilters, setFilters: setAppFilters, mapPolygon, query: appQuery } = useApp()
  const { language } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [panel, setPanel] = useState<ResultsPanel>('results')
  const [order, setOrder] = useState<ResultsOrder>('relevance')
  const [filters, setFilters] = useState<ResultsFilters>(() => createDefaultFilters(rentalMode))
  const [draftFilters, setDraftFilters] = useState<ResultsFilters>(() => createDefaultFilters(rentalMode))
  const [focusListingId, setFocusListingId] = useState('')
  const [mobileViewport, setMobileViewport] = useState(() => window.matchMedia(MOBILE_VIEWPORT).matches)

  useEffect(() => {
    const media = window.matchMedia(MOBILE_VIEWPORT)
    const update = () => setMobileViewport(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const shouldOpen = mobileViewport && location.pathname === '/buscar' && params.get('vista') !== 'mapa'
    setOpen(shouldOpen)
    if (!shouldOpen) return
    const routeMode: RentalMode = params.get('alquiler') === 'holiday' ? 'holiday' : 'long'
    const parsed = filtersFromParams(params)
    const roomTypes = (params.get('tiposHabitacion') ?? '').split('|').filter((value): value is Listing['roomType'] => ['Habitación individual', 'Habitación compartida', 'Estudio'].includes(value))
    const roomCounts = (params.get('habitaciones') ?? '').split('|').map((value): RoomCountFilter | null => {
      if (value === '10+') return value
      const count = Number(value)
      return Number.isInteger(count) && count >= 1 && count <= 10 ? count as ExactRoomCount : null
    }).filter((value): value is RoomCountFilter => value !== null)
    const routeFilters = { rentalMode: routeMode, minPrice: parsed.minPrice, maxPrice: parsed.maxPrice, minArea: parsed.roomSizeMin, maxArea: parsed.roomSizeMax, roomTypes, roomCounts }
    setFilters(routeFilters)
    setDraftFilters(routeFilters)
    setRentalMode(routeMode)
    setAppFilters(parsed)
    const routeOrder = params.get('mobileOrden') as ResultsOrder | null
    setOrder(routeOrder && orderKeys.includes(routeOrder) ? routeOrder : 'relevance')
    setFocusListingId(params.get('anuncio') ?? '')
    if (params.get('panel') === 'filtros') setPanel('filters')
    else if (params.get('panel') === 'orden') setPanel('sort')
    else if (!open) setPanel('results')
  }, [location.pathname, location.search, mobileViewport, open, setAppFilters, setRentalMode])

  useEffect(() => {
    const openListing = (event: Event) => {
      const listingId = (event as CustomEvent<{ listingId?: string }>).detail?.listingId ?? ''
      const listing = allListings.find((item) => item.id === listingId)
      if (!listing) return
      setRentalMode(listing.rentalMode)
      setFilters((current) => ({ ...current, rentalMode: listing.rentalMode }))
      setDraftFilters((current) => ({ ...current, rentalMode: listing.rentalMode }))
      const params = new URLSearchParams(location.search)
      params.delete('vista')
      params.delete('dibujar')
      params.set('alquiler', listing.rentalMode)
      params.set('anuncio', listingId)
      navigate(`/buscar?${params.toString()}`)
    }
    window.addEventListener('112233:open-mobile-listing', openListing)
    return () => window.removeEventListener('112233:open-mobile-listing', openListing)
  }, [allListings, location.search, navigate, setRentalMode])

  useEffect(() => {
    if (!open || panel !== 'results' || !focusListingId) return
    const frame = requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-listing-id="${CSS.escape(focusListingId)}"]`)?.scrollIntoView({ block: 'start' }))
    return () => cancelAnimationFrame(frame)
  }, [focusListingId, open, panel])

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (panel === 'filters') {
        setDraftFilters(filters)
        setPanel('results')
      } else if (panel !== 'results') setPanel('results')
      else navigate('/')
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', closeOnEscape) }
  }, [filters, navigate, open, panel])

  const availableListings = useMemo(() => allListings.filter((listing) => listing.status === 'Publicado' && !discarded.has(listing.id)), [allListings, discarded])
  const filteredListings = useMemo(() => {
    const params = new URLSearchParams(location.search)
    if (filters.roomTypes.length) params.set('tiposHabitacion', filters.roomTypes.join('|'))
    else params.delete('tiposHabitacion')
    params.delete('capacidades')
    if (filters.roomCounts.length) params.set('habitaciones', filters.roomCounts.join('|'))
    else params.delete('habitaciones')
    const canonicalFilters = {
      ...appFilters,
      minPrice: Math.min(filters.minPrice, filters.maxPrice),
      maxPrice: Math.max(filters.minPrice, filters.maxPrice),
      roomSizeMin: Math.min(filters.minArea, filters.maxArea),
      roomSizeMax: Math.max(filters.minArea, filters.maxArea),
      roomType: 'Cualquiera',
      roomCapacity: 'Cualquiera',
    }
    return selectMobileSearchListings({
      listings: allListings,
      discarded,
      rentalMode: filters.rentalMode ?? rentalMode,
      filters: canonicalFilters,
      polygon: mapPolygon,
      query: params.get('q') ?? appQuery,
      params,
    })
  }, [allListings, appFilters, appQuery, discarded, filters, location.search, mapPolygon, rentalMode])

  const previewFilteredListings = useMemo(() => {
    const params = new URLSearchParams(location.search)
    if (draftFilters.roomTypes.length) params.set('tiposHabitacion', draftFilters.roomTypes.join('|'))
    else params.delete('tiposHabitacion')
    params.delete('capacidades')
    if (draftFilters.roomCounts.length) params.set('habitaciones', draftFilters.roomCounts.join('|'))
    else params.delete('habitaciones')
    const canonicalFilters = {
      ...appFilters,
      minPrice: Math.min(draftFilters.minPrice, draftFilters.maxPrice),
      maxPrice: Math.max(draftFilters.minPrice, draftFilters.maxPrice),
      roomSizeMin: Math.min(draftFilters.minArea, draftFilters.maxArea),
      roomSizeMax: Math.max(draftFilters.minArea, draftFilters.maxArea),
      roomType: 'Cualquiera',
      roomCapacity: 'Cualquiera',
    }
    return selectMobileSearchListings({
      listings: allListings,
      discarded,
      rentalMode: draftFilters.rentalMode ?? rentalMode,
      filters: canonicalFilters,
      polygon: mapPolygon,
      query: params.get('q') ?? appQuery,
      params,
    })
  }, [allListings, appFilters, appQuery, discarded, draftFilters, location.search, mapPolygon, rentalMode])

  const listings = useMemo(() => [...filteredListings].sort((a, b) => {
    if (order === 'cheap') return a.price - b.price
    if (order === 'expensive') return b.price - a.price
    if (order === 'saved-new') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || +new Date(b.publishedAt) - +new Date(a.publishedAt)
    if (order === 'saved-old') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || +new Date(a.publishedAt) - +new Date(b.publishedAt)
    if (order === 'reduced') return a.price - b.price || b.views - a.views
    if (order === 'sqm-cheap') return a.price / Math.max(1, a.roomSizeM2 ?? Number.POSITIVE_INFINITY) - b.price / Math.max(1, b.roomSizeM2 ?? Number.POSITIVE_INFINITY)
    if (order === 'sqm-expensive') return b.price / Math.max(1, b.roomSizeM2 ?? Number.NEGATIVE_INFINITY) - a.price / Math.max(1, a.roomSizeM2 ?? Number.NEGATIVE_INFINITY)
    if (order === 'area-large') return (b.roomSizeM2 ?? Number.NEGATIVE_INFINITY) - (a.roomSizeM2 ?? Number.NEGATIVE_INFINITY)
    if (order === 'area-small') return (a.roomSizeM2 ?? Number.POSITIVE_INFINITY) - (b.roomSizeM2 ?? Number.POSITIVE_INFINITY)
    if (order === 'floor-high') return stableFloor(b) - stableFloor(a)
    if (order === 'floor-low') return stableFloor(a) - stableFloor(b)
    return +new Date(b.publishedAt) - +new Date(a.publishedAt)
  }), [favorites, filteredListings, order])
  const orderedListings = useMemo(() => focusListingId ? [...listings].sort((left, right) => Number(right.id === focusListingId) - Number(left.id === focusListingId)) : listings, [focusListingId, listings])

  if (!open) return null
  const t = resultsCopy[language] as ResultsCopy
  const contact = () => {
    if (currentUser) return
    navigate('/acceso')
  }
  const openMap = () => {
    const params = new URLSearchParams(location.search)
    params.delete('panel')
    params.set('alquiler', filters.rentalMode ?? rentalMode)
    params.set('vista', 'mapa')
    navigate(`/buscar?${params.toString()}`)
  }
  const chooseRentalMode = (mode: RentalMode) => {
    setDraftFilters((current) => ({ ...current, rentalMode: mode }))
  }
  const applyFilters = () => {
    const nextMode = draftFilters.rentalMode ?? rentalMode
    const nextFilters = {
      ...appFilters,
      minPrice: Math.min(draftFilters.minPrice, draftFilters.maxPrice),
      maxPrice: Math.max(draftFilters.minPrice, draftFilters.maxPrice),
      roomSizeMin: Math.min(draftFilters.minArea, draftFilters.maxArea),
      roomSizeMax: Math.max(draftFilters.minArea, draftFilters.maxArea),
      roomType: 'Cualquiera',
      roomCapacity: 'Cualquiera',
    }
    setFilters(draftFilters)
    setRentalMode(nextMode)
    setAppFilters(nextFilters)
    const params = filtersToParams(nextFilters, new URLSearchParams(location.search))
    params.set('alquiler', nextMode)
    params.delete('panel')
    if (draftFilters.roomTypes.length) params.set('tiposHabitacion', draftFilters.roomTypes.join('|'))
    else params.delete('tiposHabitacion')
    params.delete('capacidades')
    if (draftFilters.roomCounts.length) params.set('habitaciones', draftFilters.roomCounts.join('|'))
    else params.delete('habitaciones')
    navigate(`/buscar?${params.toString()}`, { replace: true })
    setPanel('results')
  }
  const clearFilters = () => setDraftFilters((current) => ({
    ...createDefaultFilters(current.rentalMode),
    minPrice: defaultFilters.minPrice,
    maxPrice: defaultFilters.maxPrice,
    minArea: defaultFilters.roomSizeMin,
    maxArea: defaultFilters.roomSizeMax,
  }))
  const applyOrder = (value: ResultsOrder) => {
    setOrder(value)
    const canonicalSort = value === 'cheap' ? 'Precio más bajo' : value === 'expensive' ? 'Precio más alto' : 'Relevancia'
    const nextFilters = { ...appFilters, sort: canonicalSort }
    setAppFilters(nextFilters)
    const params = filtersToParams(nextFilters, new URLSearchParams(location.search))
    params.set('mobileOrden', value)
    params.delete('panel')
    navigate(`/buscar?${params.toString()}`, { replace: true })
    setPanel('results')
  }

  return createPortal(<section className="m2-results notranslate" translate="no" data-testid="mobile-results">
    {panel === 'results' ? <><header className="m2-results__header"><button type="button" onClick={() => navigate('/')} aria-label={t.back}><ChevronLeft /></button><div><strong>{t.header(listings.length)}</strong><small>{t.zone}</small></div></header>
      <div className="m2-results__toolbar"><button type="button" onClick={() => { setDraftFilters(filters); setPanel('filters') }}><SlidersHorizontal />{t.filters}</button><button type="button" onClick={() => setPanel('sort')}><ArrowDownUp />{t.order}</button><button type="button" onClick={openMap}><Map />{t.map}</button></div>
      <div className="m2-results__summary"><span>{t.showing(listings.length, availableListings.length)}</span><b>{orderLabel(t, order)}</b></div><div className="m2-results__list">{orderedListings.length ? orderedListings.map((listing, index) => <MobileResultCard key={listing.id} listing={listing} index={index} language={language} favorite={favorites.has(listing.id)} onFavorite={() => toggleFavorite(listing.id)} onDiscard={() => discardListing(listing.id)} onContact={contact} onOpen={() => {
        if (listing.isExternal && listing.sourceUrl) {
          window.open(listing.sourceUrl, '_blank', 'noopener,noreferrer')
          return
        }
        navigate(`/habitacion/${listing.id}`)
      }} />) : <div className="m2-results__empty">{t.empty}</div>}</div></> : null}

    {panel === 'sort' ? <section className="m2-results-panel"><header><button type="button" onClick={() => setPanel('results')} aria-label={t.close}><X /></button><strong>{t.order}</strong></header><div className="m2-results-sort" role="radiogroup">{orderKeys.map((value) => <button key={value} type="button" role="radio" aria-checked={order === value} onClick={() => applyOrder(value)}><span>{orderLabel(t, value)}</span><i>{order === value ? '●' : ''}</i></button>)}</div></section> : null}

    {panel === 'filters' ? <section className="m2-results-panel m2-results-filter"><header><button type="button" onClick={() => { setDraftFilters(filters); setPanel('results') }} aria-label={t.close}><X /></button><strong>{t.filters}</strong><button type="button" className="m2-results-filter__clear" onClick={clearFilters}>{t.clear}</button></header><div className="m2-results-filter__scroll">
      <div className="m2-results-filter__transaction" role="group" aria-label={`${t.vivienda} / ${t.turismo}`}><button type="button" className={cn(draftFilters.rentalMode === 'long' && 'is-active')} aria-pressed={draftFilters.rentalMode === 'long'} onClick={() => chooseRentalMode('long')}>{t.vivienda}</button><button type="button" className={cn(draftFilters.rentalMode === 'holiday' && 'is-active')} aria-pressed={draftFilters.rentalMode === 'holiday'} onClick={() => chooseRentalMode('holiday')}>{t.turismo}</button></div>
      <fieldset><legend>{t.price}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.price} ${t.min}`} type="number" min="0" step="25" value={draftFilters.minPrice} onChange={(event) => setDraftFilters((current) => ({ ...current, minPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.price} ${t.max}`} type="number" min="0" step="25" value={draftFilters.maxPrice} onChange={(event) => setDraftFilters((current) => ({ ...current, maxPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.area}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.area} ${t.min}`} type="number" min="0" value={draftFilters.minArea} onChange={(event) => setDraftFilters((current) => ({ ...current, minArea: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.area} ${t.max}`} type="number" min="0" value={draftFilters.maxArea} onChange={(event) => setDraftFilters((current) => ({ ...current, maxArea: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.rooms}</legend><div className="m2-results-filter__checks m2-results-filter__checks--rooms">{roomCountOptions.map((value) => { const label = value === '10+' ? t.moreThanTenRooms : t.roomCount(value); return <label key={String(value)}><input type="checkbox" checked={draftFilters.roomCounts.includes(value)} onChange={() => setDraftFilters((current) => ({ ...current, roomCounts: toggleValue(current.roomCounts, value) }))} /><span>{label}</span></label> })}</div></fieldset>
      <fieldset><legend>{t.housingType}</legend><div className="m2-results-filter__checks">{([['Habitación individual', t.individual], ['Habitación compartida', t.shared], ['Estudio', t.studio]] as const).map(([value, label]) => <label key={value}><input type="checkbox" checked={draftFilters.roomTypes.includes(value)} onChange={() => setDraftFilters((current) => ({ ...current, roomTypes: toggleValue(current.roomTypes, value) }))} /><span>{label}</span></label>)}</div></fieldset>
    </div><footer><button type="button" onClick={applyFilters}>{t.showListings} · {previewFilteredListings.length}</button></footer></section> : null}
  </section>, document.body)
}
