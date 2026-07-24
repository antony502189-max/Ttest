import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react'
import {
  ArrowDownUp,
  ArrowLeft,
  BedDouble,
  ChevronDown,
  Heart,
  Map,
  MessageSquare,
  Phone,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-react'
import { useApp } from '@/contexts/app-context'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'
import '@/mobile-listings-experience.css'

type Panel = 'results' | 'filters' | 'sort'
type TransactionMode = 'buy' | 'rent'
type SortKey = 'relevance' | 'cheap' | 'expensive' | 'saved-new' | 'saved-old' | 'reduced' | 'sqm-cheap' | 'sqm-expensive' | 'area-large' | 'area-small' | 'floor-high' | 'floor-low'
type AppLanguage = 'es' | 'en' | 'ru'
type RentalKind = 'long' | 'holiday'

type LocalFilters = {
  transaction: TransactionMode
  minPrice: number
  maxPrice: number
  minArea: number
  maxArea: number
  roomTypes: string[]
  roomCounts: number[]
  rentalKinds: RentalKind[]
}

const LANGUAGE_KEY = '112233:mobile-language:v2'

const text = {
  es: {
    back: 'Volver', results: 'viviendas', zone: 'Tenerife', filters: 'Filtros', order: 'Orden', map: 'Mapa', showing: 'Mostrando', of: 'de', top: 'Destacado',
    contact: 'Contactar', call: 'Llamar', discard: 'Descartar', favorite: 'Favorito', buy: 'Comprar', rent: 'Alquilar', propertyType: 'Tipo de inmueble', residential: 'Viviendas',
    price: 'Precio', area: 'Superficie', min: 'Mín', max: 'Máx', housingType: 'Tipo de vivienda', rooms: 'Número de habitaciones', oneRoom: '1 habitación', twoRooms: '2 habitaciones',
    individual: 'Habitaciones individuales', shared: 'Habitaciones compartidas', studio: 'Estudios', rentalType: 'Tipo de alquiler', long: 'Larga estancia', holiday: 'Turismo',
    showListings: 'Ver anuncios', clear: 'Limpiar', sortTitle: 'Orden', empty: 'No hay anuncios que coincidan con estos filtros.',
    relevance: 'Relevancia', cheap: 'Más baratos', expensive: 'Más caros', savedNew: 'Guardados recientemente', savedOld: 'Guardados anteriormente', reduced: 'Precio rebajado',
    sqmCheap: 'Menor precio por m²', sqmExpensive: 'Mayor precio por m²', areaLarge: 'Mayor superficie', areaSmall: 'Menor superficie', floorHigh: 'Plantas altas', floorLow: 'Plantas bajas',
  },
  en: {
    back: 'Back', results: 'properties', zone: 'Tenerife', filters: 'Filters', order: 'Order', map: 'Map', showing: 'Showing', of: 'of', top: 'Featured',
    contact: 'Contact', call: 'Call', discard: 'Discard', favorite: 'Favorite', buy: 'Buy', rent: 'Rent', propertyType: 'Property type', residential: 'Residential properties',
    price: 'Price', area: 'Area', min: 'Min', max: 'Max', housingType: 'Property category', rooms: 'Number of rooms', oneRoom: '1 room', twoRooms: '2 rooms',
    individual: 'Individual rooms', shared: 'Shared rooms', studio: 'Studios', rentalType: 'Rental type', long: 'Long stay', holiday: 'Tourism',
    showListings: 'View listings', clear: 'Clear', sortTitle: 'Order', empty: 'No listings match these filters.',
    relevance: 'Relevance', cheap: 'Cheapest', expensive: 'Most expensive', savedNew: 'Saved recently', savedOld: 'Saved earlier', reduced: 'Reduced price',
    sqmCheap: 'Lowest price per m²', sqmExpensive: 'Highest price per m²', areaLarge: 'Largest area', areaSmall: 'Smallest area', floorHigh: 'Upper floors', floorLow: 'Lower floors',
  },
  ru: {
    back: 'Назад', results: 'объявлений', zone: 'Тенерифе', filters: 'Фильтры', order: 'Порядок', map: 'Карта', showing: 'Просмотр', of: 'из', top: 'Топ',
    contact: 'Связаться', call: 'Позвонить', discard: 'Скрыть', favorite: 'Избранное', buy: 'Купить', rent: 'Снять', propertyType: 'Тип недвижимости', residential: 'Жилые объекты',
    price: 'Цена', area: 'Площадь', min: 'Мин', max: 'Макс', housingType: 'Тип жилья', rooms: 'Количество комнат', oneRoom: '1 комната', twoRooms: '2 комнаты',
    individual: 'Отдельные комнаты', shared: 'Общие комнаты', studio: 'Студии', rentalType: 'Тип аренды', long: 'Долгосрочная', holiday: 'Туризм',
    showListings: 'Перейти к объявлениям', clear: 'Сбросить', sortTitle: 'Порядок', empty: 'Нет объявлений, подходящих под выбранные фильтры.',
    relevance: 'Релевантность', cheap: 'Дешевые', expensive: 'Дорогие', savedNew: 'Сохраненные недавно', savedOld: 'Сохраненные раньше', reduced: 'Со сниженной ценой',
    sqmCheap: 'Дешевые евро/м²', sqmExpensive: 'Дорогие евро/м²', areaLarge: 'С большей площадью', areaSmall: 'С меньшей площадью', floorHigh: 'Верхние этажи', floorLow: 'Нижние этажи',
  },
} as const

type Copy = (typeof text)[AppLanguage]

const defaultLocalFilters: LocalFilters = {
  transaction: 'rent',
  minPrice: 0,
  maxPrice: 1500,
  minArea: 0,
  maxArea: 50,
  roomTypes: [],
  roomCounts: [],
  rentalKinds: ['long', 'holiday'],
}

const sortKeys: SortKey[] = ['relevance', 'cheap', 'expensive', 'saved-new', 'saved-old', 'reduced', 'sqm-cheap', 'sqm-expensive', 'area-large', 'area-small', 'floor-high', 'floor-low']

function getLanguage(): AppLanguage {
  try {
    const value = localStorage.getItem(LANGUAGE_KEY)
    return value === 'en' || value === 'ru' ? value : 'es'
  } catch {
    return 'es'
  }
}

function getStableFloor(listing: Listing) {
  let value = 0
  for (const char of listing.id) value = (value * 31 + char.charCodeAt(0)) % 11
  return value
}

function sortLabel(copy: Copy, key: SortKey) {
  const labels: Record<SortKey, string> = {
    relevance: copy.relevance,
    cheap: copy.cheap,
    expensive: copy.expensive,
    'saved-new': copy.savedNew,
    'saved-old': copy.savedOld,
    reduced: copy.reduced,
    'sqm-cheap': copy.sqmCheap,
    'sqm-expensive': copy.sqmExpensive,
    'area-large': copy.areaLarge,
    'area-small': copy.areaSmall,
    'floor-high': copy.floorHigh,
    'floor-low': copy.floorLow,
  }
  return labels[key]
}

function toggleArrayValue<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value]
}

function waitForElement(selector: string, timeout = 2500): Promise<HTMLElement | null> {
  const immediate = document.querySelector<HTMLElement>(selector)
  if (immediate) return Promise.resolve(immediate)
  return new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      const element = document.querySelector<HTMLElement>(selector)
      if (!element) return
      observer.disconnect()
      window.clearTimeout(timer)
      resolve(element)
    })
    observer.observe(document.body, { childList: true, subtree: true })
    const timer = window.setTimeout(() => {
      observer.disconnect()
      resolve(null)
    }, timeout)
  })
}

function ListingCard({ listing, copy, favorite, onFavorite, onDiscard }: {
  listing: Listing
  copy: Copy
  favorite: boolean
  onFavorite: () => void
  onDiscard: () => void
}) {
  const phone = listing.contactPhone?.replace(/\s+/g, '')
  const whatsapp = listing.contactWhatsapp?.replace(/\D/g, '')
  const openContact = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    if (whatsapp) window.open(`https://wa.me/${whatsapp}`, '_blank', 'noopener,noreferrer')
    else if (listing.contactEmail) window.location.href = `mailto:${listing.contactEmail}`
  }
  return <article className="ml-card" data-listing-id={listing.id}>
    <div className="ml-card__image-wrap">
      <img src={listing.images[0]} alt={listing.title} loading="lazy" />
      <span className="ml-card__photo-count">1/{listing.images.length}</span>
      <span className="ml-card__featured">{copy.top}</span>
    </div>
    <div className="ml-card__body">
      <div className="ml-card__media-icons" aria-hidden="true"><span>▧</span><span>⌂</span><span>3D</span><span>▣</span><span>⌖</span></div>
      <h2>{listing.title}</h2>
      <strong className="ml-card__price">{new Intl.NumberFormat('es-ES').format(listing.price)} € <small>/{listing.cadence}</small></strong>
      <p className="ml-card__meta"><span>{listing.roomType}</span><span>{listing.roomSizeM2} m²</span><span>{listing.area}</span></p>
      <span className="ml-card__tag">{listing.advertiserType}</span>
      <div className="ml-card__actions">
        <button type="button" onClick={openContact}><MessageSquare />{copy.contact}</button>
        {phone ? <a href={`tel:${phone}`} onClick={(event) => event.stopPropagation()}><Phone />{copy.call}</a> : null}
        <button type="button" className="ml-icon-action" onClick={(event) => { event.stopPropagation(); onDiscard() }} aria-label={copy.discard}><Trash2 /></button>
        <button type="button" className={cn('ml-icon-action', favorite && 'is-active')} onClick={(event) => { event.stopPropagation(); onFavorite() }} aria-label={copy.favorite} aria-pressed={favorite}><Heart /></button>
      </div>
    </div>
  </article>
}

export function MobileListingsExperience() {
  const { allListings, favorites, toggleFavorite, discarded, discardListing } = useApp()
  const [open, setOpen] = useState(false)
  const [panel, setPanel] = useState<Panel>('results')
  const [language, setLanguage] = useState<AppLanguage>(getLanguage)
  const [filters, setFilters] = useState<LocalFilters>(defaultLocalFilters)
  const [sort, setSort] = useState<SortKey>('relevance')
  const copy = text[language]

  useEffect(() => {
    const onStorage = () => setLanguage(getLanguage())
    window.addEventListener('storage', onStorage)
    const interval = window.setInterval(() => setLanguage((current) => {
      const next = getLanguage()
      return next === current ? current : next
    }), 400)
    return () => { window.removeEventListener('storage', onStorage); window.clearInterval(interval) }
  }, [])

  useEffect(() => {
    const clickHandler = (event: MouseEvent) => {
      if (!window.matchMedia('(max-width: 767px)').matches) return
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('button, a') : null
      if (!target) return
      const isMainSearch = target.matches('[data-testid="open-location"]')
      const isMapList = Boolean(target.closest('.m2-map-toolbar')) && /listado|list|перечень/i.test(target.textContent ?? '')
      if (!isMainSearch && !isMapList) return
      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation()
      setLanguage(getLanguage())
      setPanel('results')
      setOpen(true)
    }
    document.addEventListener('click', clickHandler, true)
    return () => document.removeEventListener('click', clickHandler, true)
  }, [])

  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previous }
  }, [open])

  const filtered = useMemo(() => allListings.filter((listing) => {
    if (listing.status !== 'Publicado' || discarded.has(listing.id)) return false
    if (listing.price < filters.minPrice || listing.price > filters.maxPrice) return false
    if (listing.roomSizeM2 < filters.minArea || listing.roomSizeM2 > filters.maxArea) return false
    if (filters.roomTypes.length && !filters.roomTypes.includes(listing.roomType)) return false
    if (filters.roomCounts.length && !filters.roomCounts.includes(listing.roomCapacity)) return false
    if (filters.transaction === 'rent' && filters.rentalKinds.length && !filters.rentalKinds.includes(listing.rentalMode)) return false
    return true
  }), [allListings, discarded, filters])

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    if (sort === 'cheap') return a.price - b.price
    if (sort === 'expensive') return b.price - a.price
    if (sort === 'saved-new') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
    if (sort === 'saved-old') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || new Date(a.publishedAt).getTime() - new Date(b.publishedAt).getTime()
    if (sort === 'reduced') return a.price - b.price || b.views - a.views
    if (sort === 'sqm-cheap') return a.price / Math.max(1, a.roomSizeM2) - b.price / Math.max(1, b.roomSizeM2)
    if (sort === 'sqm-expensive') return b.price / Math.max(1, b.roomSizeM2) - a.price / Math.max(1, a.roomSizeM2)
    if (sort === 'area-large') return b.roomSizeM2 - a.roomSizeM2
    if (sort === 'area-small') return a.roomSizeM2 - b.roomSizeM2
    if (sort === 'floor-high') return getStableFloor(b) - getStableFloor(a)
    if (sort === 'floor-low') return getStableFloor(a) - getStableFloor(b)
    return new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  }), [favorites, filtered, sort])

  const openMap = async () => {
    setOpen(false)
    if (document.querySelector('.m2-map-screen')) return
    document.querySelector<HTMLButtonElement>('.m2-select-row')?.click()
    const mapButton = await waitForElement('[data-testid="search-map"]')
    mapButton?.click()
  }

  if (!open) return null

  return <section className="ml-shell notranslate" translate="no" aria-label={copy.results}>
    {panel === 'results' ? <>
      <header className="ml-results-header">
        <button type="button" onClick={() => setOpen(false)} aria-label={copy.back}><ArrowLeft /></button>
        <div><strong>{sorted.length} {copy.results}</strong><small>{copy.zone}</small></div>
      </header>
      <nav className="ml-results-toolbar" aria-label={`${copy.filters}, ${copy.order}, ${copy.map}`}>
        <button type="button" onClick={() => setPanel('filters')}><SlidersHorizontal />{copy.filters}</button>
        <button type="button" onClick={() => setPanel('sort')}><ArrowDownUp />{copy.order}</button>
        <button type="button" onClick={openMap}><Map />{copy.map}</button>
      </nav>
      <div className="ml-results-summary">{copy.showing} {sorted.length} {copy.of} {allListings.filter((listing) => listing.status === 'Publicado' && !discarded.has(listing.id)).length}</div>
      <main className="ml-results-list">
        {sorted.length ? sorted.map((listing) => <ListingCard key={listing.id} listing={listing} copy={copy} favorite={favorites.has(listing.id)} onFavorite={() => toggleFavorite(listing.id)} onDiscard={() => discardListing(listing.id)} />) : <div className="ml-empty">{copy.empty}</div>}
      </main>
    </> : null}

    {panel === 'sort' ? <div className="ml-sheet-page">
      <header><button type="button" onClick={() => setPanel('results')} aria-label={copy.close}><X /></button><strong>{copy.sortTitle}</strong></header>
      <div className="ml-sort-list" role="radiogroup" aria-label={copy.sortTitle}>{sortKeys.map((key) => <button key={key} type="button" role="radio" aria-checked={sort === key} onClick={() => { setSort(key); setPanel('results') }}><span>{sortLabel(copy, key)}</span><i>{sort === key ? '●' : ''}</i></button>)}</div>
    </div> : null}

    {panel === 'filters' ? <div className="ml-sheet-page ml-filter-page">
      <header><button type="button" onClick={() => setPanel('results')} aria-label={copy.close}><X /></button><strong>{copy.filters}</strong><button type="button" className="ml-clear" onClick={() => setFilters(defaultLocalFilters)}>{copy.clear}</button></header>
      <div className="ml-filter-scroll">
        <div className="ml-transaction" role="group" aria-label={`${copy.buy}/${copy.rent}`}>
          <button type="button" className={cn(filters.transaction === 'buy' && 'is-active')} aria-pressed={filters.transaction === 'buy'} onClick={() => setFilters((current) => ({ ...current, transaction: 'buy' }))}>{copy.buy}</button>
          <button type="button" className={cn(filters.transaction === 'rent' && 'is-active')} aria-pressed={filters.transaction === 'rent'} onClick={() => setFilters((current) => ({ ...current, transaction: 'rent' }))}>{copy.rent}</button>
        </div>
        <label className="ml-select-field"><span>{copy.propertyType}</span><select defaultValue="residential"><option value="residential">{copy.residential}</option></select><ChevronDown /></label>
        <fieldset><legend>{copy.price}</legend><div className="ml-two-fields"><label><span>{copy.min}</span><input type="number" min="0" step="25" value={filters.minPrice} onChange={(event) => setFilters((current) => ({ ...current, minPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{copy.max}</span><input type="number" min="0" step="25" value={filters.maxPrice} onChange={(event) => setFilters((current) => ({ ...current, maxPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
        <fieldset><legend>{copy.area}</legend><div className="ml-two-fields"><label><span>{copy.min}</span><input type="number" min="0" step="1" value={filters.minArea} onChange={(event) => setFilters((current) => ({ ...current, minArea: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{copy.max}</span><input type="number" min="0" step="1" value={filters.maxArea} onChange={(event) => setFilters((current) => ({ ...current, maxArea: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
        <fieldset><legend>{copy.rooms}</legend><div className="ml-check-list"><label><input type="checkbox" checked={filters.roomCounts.includes(1)} onChange={() => setFilters((current) => ({ ...current, roomCounts: toggleArrayValue(current.roomCounts, 1) }))} /><span>{copy.oneRoom}</span></label><label><input type="checkbox" checked={filters.roomCounts.includes(2)} onChange={() => setFilters((current) => ({ ...current, roomCounts: toggleArrayValue(current.roomCounts, 2) }))} /><span>{copy.twoRooms}</span></label></div></fieldset>
        <fieldset><legend>{copy.housingType}</legend><div className="ml-check-list"><label><input type="checkbox" checked={filters.roomTypes.includes('Habitación individual')} onChange={() => setFilters((current) => ({ ...current, roomTypes: toggleArrayValue(current.roomTypes, 'Habitación individual') }))} /><span>{copy.individual}</span></label><label><input type="checkbox" checked={filters.roomTypes.includes('Habitación compartida')} onChange={() => setFilters((current) => ({ ...current, roomTypes: toggleArrayValue(current.roomTypes, 'Habitación compartida') }))} /><span>{copy.shared}</span></label><label><input type="checkbox" checked={filters.roomTypes.includes('Estudio')} onChange={() => setFilters((current) => ({ ...current, roomTypes: toggleArrayValue(current.roomTypes, 'Estudio') }))} /><span>{copy.studio}</span></label></div></fieldset>
        {filters.transaction === 'rent' ? <fieldset><legend>{copy.rentalType}</legend><div className="ml-check-list"><label><input type="checkbox" checked={filters.rentalKinds.includes('long')} onChange={() => setFilters((current) => ({ ...current, rentalKinds: toggleArrayValue(current.rentalKinds, 'long') }))} /><span>{copy.long}</span></label><label><input type="checkbox" checked={filters.rentalKinds.includes('holiday')} onChange={() => setFilters((current) => ({ ...current, rentalKinds: toggleArrayValue(current.rentalKinds, 'holiday') }))} /><span>{copy.holiday}</span></label></div></fieldset> : null}
      </div>
      <div className="ml-filter-footer"><button type="button" onClick={() => setPanel('results')}>{copy.showListings} · {sorted.length}</button></div>
    </div> : null}
  </section>
}
