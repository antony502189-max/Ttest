import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { createPortal } from 'react-dom'
import {
  ArrowDownUp,
  ChevronDown,
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
import type { Listing, RentalMode } from '@/types'
import { cn } from '@/lib/utils'
import '@/mobile-search-results.css'

type ResultsLanguage = 'es' | 'en' | 'ru'
type ResultsPanel = 'results' | 'filters' | 'sort'
type ResultsOrder = 'relevance' | 'cheap' | 'expensive' | 'saved-new' | 'saved-old' | 'reduced' | 'sqm-cheap' | 'sqm-expensive' | 'area-large' | 'area-small' | 'floor-high' | 'floor-low'
type ResultsFilters = {
  rentalMode: RentalMode | null
  minPrice: number
  maxPrice: number
  minArea: number
  maxArea: number
  roomTypes: Listing['roomType'][]
  roomCounts: number[]
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
    vivienda: 'Vivienda', turismo: 'Turismo', propertyType: 'Tipo de inmueble', residential: 'Viviendas', price: 'Precio', area: 'Superficie', min: 'Mín', max: 'Máx', housingType: 'Tipo de vivienda', rooms: 'Número de habitaciones', oneRoom: '1 habitación', twoRooms: '2 habitaciones',
    individual: 'Habitaciones individuales', shared: 'Habitaciones compartidas', studio: 'Estudios', showListings: 'Ver anuncios', residents: 'residentes',
    relevance: 'Relevancia', cheap: 'Más baratos', expensive: 'Más caros', savedNew: 'Guardados recientemente', savedOld: 'Guardados anteriormente', reduced: 'Precio rebajado', sqmCheap: 'Menor precio por m²', sqmExpensive: 'Mayor precio por m²', areaLarge: 'Mayor superficie', areaSmall: 'Menor superficie', floorHigh: 'Plantas altas', floorLow: 'Plantas bajas',
  },
  en: {
    header: (count: number) => `${count} properties in Tenerife`, zone: 'Your selected area', filters: 'Filters', order: 'Order', map: 'Map', showing: (count: number, total: number) => `Viewing ${count} of ${total} properties`, top: 'Featured',
    contact: 'Contact', call: 'Call', favorite: 'Add to favorites', unfavorite: 'Remove from favorites', discard: 'Hide listing', photo: 'Next photo', back: 'Back', close: 'Close', clear: 'Clear', empty: 'No listings match these filters.',
    vivienda: 'Housing', turismo: 'Tourism', propertyType: 'Property type', residential: 'Residential properties', price: 'Price', area: 'Area', min: 'Min', max: 'Max', housingType: 'Property category', rooms: 'Number of rooms', oneRoom: '1 room', twoRooms: '2 rooms',
    individual: 'Individual rooms', shared: 'Shared rooms', studio: 'Studios', showListings: 'View listings', residents: 'residents',
    relevance: 'Relevance', cheap: 'Cheapest', expensive: 'Most expensive', savedNew: 'Saved recently', savedOld: 'Saved earlier', reduced: 'Reduced price', sqmCheap: 'Lowest price per m²', sqmExpensive: 'Highest price per m²', areaLarge: 'Largest area', areaSmall: 'Smallest area', floorHigh: 'Upper floors', floorLow: 'Lower floors',
  },
  ru: {
    header: (count: number) => `${count} объявлений на Тенерифе`, zone: 'Ваша выделенная зона', filters: 'Фильтры', order: 'Порядок', map: 'Карта', showing: (count: number, total: number) => `Просмотр ${count} из ${total} объявлений`, top: 'Топ',
    contact: 'Связаться', call: 'Позвонить', favorite: 'Добавить в избранное', unfavorite: 'Убрать из избранного', discard: 'Скрыть объявление', photo: 'Следующая фотография', back: 'Назад', close: 'Закрыть', clear: 'Сбросить', empty: 'Нет объявлений, подходящих под выбранные фильтры.',
    vivienda: 'Жильё', turismo: 'Туризм', propertyType: 'Тип недвижимости', residential: 'Жилые объекты', price: 'Цена', area: 'Площадь', min: 'Мин', max: 'Макс', housingType: 'Тип жилья', rooms: 'Количество комнат', oneRoom: '1 комната', twoRooms: '2 комнаты',
    individual: 'Отдельные комнаты', shared: 'Общие комнаты', studio: 'Студии', showListings: 'Перейти к объявлениям', residents: 'жильцов',
    relevance: 'Релевантность', cheap: 'Дешевые', expensive: 'Дорогие', savedNew: 'Сохраненные недавно', savedOld: 'Сохраненные раньше', reduced: 'Со сниженной ценой', sqmCheap: 'Дешевые евро/м²', sqmExpensive: 'Дорогие евро/м²', areaLarge: 'С большей площадью', areaSmall: 'С меньшей площадью', floorHigh: 'Верхние этажи', floorLow: 'Нижние этажи',
  },
} as const

type ResultsCopy = typeof resultsCopy.es

const fallbackImage = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23282828"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%235d655f"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23727b74"/%3E%3C/svg%3E'

function currentLanguage(): ResultsLanguage {
  const stored = localStorage.getItem('112233:mobile-language:v2')
  return stored === 'en' || stored === 'ru' ? stored : 'es'
}

function selectedHomeRentalMode(): RentalMode | null {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.m2-mode-switch > button'))
  if (buttons[0]?.getAttribute('aria-pressed') === 'true') return 'long'
  if (buttons[1]?.getAttribute('aria-pressed') === 'true') return 'holiday'
  return null
}

function syncHomeRentalMode(mode: RentalMode) {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.m2-mode-switch > button'))
  const button = mode === 'long' ? buttons[0] : buttons[1]
  if (button && button.getAttribute('aria-pressed') !== 'true') button.click()
}

function imageFallback(event: SyntheticEvent<HTMLImageElement>) {
  event.currentTarget.src = fallbackImage
}

function formatPrice(listing: Listing, language: ResultsLanguage) {
  const value = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES').format(listing.price)
  const cadence = listing.cadence === 'noche' ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche' : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'
  return `${value} € / ${cadence}`
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

function waitForElement(selector: string, timeout = 2500): Promise<HTMLElement | null> {
  const current = document.querySelector<HTMLElement>(selector)
  if (current) return Promise.resolve(current)
  return new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      const element = document.querySelector<HTMLElement>(selector)
      if (!element) return
      observer.disconnect(); window.clearTimeout(timer); resolve(element)
    })
    observer.observe(document.body, { childList: true, subtree: true })
    const timer = window.setTimeout(() => { observer.disconnect(); resolve(null) }, timeout)
  })
}

function openExistingAuthentication() {
  const openLogin = () => document.querySelector<HTMLButtonElement>('.m2-menu > .m2-primary')?.click()
  if (document.querySelector('.m2-menu')) return requestAnimationFrame(openLogin)
  document.querySelector<HTMLButtonElement>('.m2-bottom-nav button:last-child')?.click()
  requestAnimationFrame(() => requestAnimationFrame(openLogin))
}

function MobileResultCard({ listing, index, language, favorite, onFavorite, onDiscard, onContact }: {
  listing: Listing; index: number; language: ResultsLanguage; favorite: boolean; onFavorite: () => void; onDiscard: () => void; onContact: () => void
}) {
  const t = resultsCopy[language] as ResultsCopy
  const [imageIndex, setImageIndex] = useState(0)
  const images = listing.images.length ? listing.images : [fallbackImage]
  const nextImage = () => setImageIndex((current) => (current + 1) % images.length)
  return <article className="m2-result-card" data-listing-id={listing.id}>
    <div className="m2-result-card__media"><button type="button" className="m2-result-card__image-button" onClick={nextImage} aria-label={`${t.photo}: ${listing.title}`}><MediaImage src={images[imageIndex]} onError={imageFallback} alt={`${listing.title}, ${imageIndex + 1}/${images.length}`} loading="lazy" /></button>{index < 2 ? <span className="m2-result-card__top">{t.top}</span> : null}<span className="m2-result-card__counter"><ImageIcon />{imageIndex + 1}/{images.length}</span>{images.length > 1 ? <button type="button" className="m2-result-card__next" onClick={nextImage} aria-label={t.photo}><ChevronRight /></button> : null}</div>
    <div className="m2-result-card__content"><p className="m2-result-card__location"><MapPin />{listing.area}, {listing.city}</p><h2>{listing.title}</h2><strong className="m2-result-card__price">{formatPrice(listing, language)}</strong><p className="m2-result-card__facts">{listing.roomType} · {listing.roomSizeM2} m² · {listing.currentResidents} {t.residents}</p><p className="m2-result-card__availability">{listing.available}</p><div className="m2-result-card__badges">{listing.restrictions.slice(0, 2).map((restriction) => <span key={restriction}>{restriction}</span>)}</div>
      <div className="m2-result-card__actions"><button type="button" onClick={onContact}><MessageCircle />{t.contact}</button>{listing.showPhone && listing.contactPhone ? <a href={`tel:${listing.contactPhone}`}><Phone />{t.call}</a> : null}<button type="button" className="m2-result-card__discard" onClick={onDiscard} aria-label={t.discard}><Trash2 /></button><button type="button" className={cn('m2-result-card__favorite', favorite && 'is-active')} onClick={onFavorite} aria-label={favorite ? t.unfavorite : t.favorite} aria-pressed={favorite}><Heart /></button></div>
    </div>
  </article>
}

export function MobileSearchResults() {
  const { allListings, discarded, discardListing, favorites, toggleFavorite, currentUser, setRentalMode } = useApp()
  const [open, setOpen] = useState(false)
  const [panel, setPanel] = useState<ResultsPanel>('results')
  const [language, setLanguage] = useState<ResultsLanguage>('es')
  const [order, setOrder] = useState<ResultsOrder>('relevance')
  const [filters, setFilters] = useState<ResultsFilters>(() => createDefaultFilters())

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!window.matchMedia('(max-width: 767px)').matches) return
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('button, a') : null
      if (!target) return
      const mainSearch = target.matches('[data-testid="open-location"]')
      const mapList = Boolean(target.closest('.m2-map-toolbar')) && /listado|list|перечень/i.test(target.textContent ?? '')
      if (!mainSearch && !mapList) return
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation()
      if (mainSearch) {
        const selectedMode = selectedHomeRentalMode()
        setFilters((current) => ({ ...current, rentalMode: selectedMode }))
        if (selectedMode) setRentalMode(selectedMode)
      }
      setLanguage(currentLanguage()); setPanel('results'); setOpen(true)
    }
    document.addEventListener('click', handleClick, true)
    return () => document.removeEventListener('click', handleClick, true)
  }, [setRentalMode])

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (panel !== 'results') setPanel('results')
      else setOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', closeOnEscape) }
  }, [open, panel])

  const availableListings = useMemo(() => allListings.filter((listing) => listing.status === 'Publicado' && !discarded.has(listing.id)), [allListings, discarded])
  const filteredListings = useMemo(() => {
    const minPrice = Math.min(filters.minPrice, filters.maxPrice)
    const maxPrice = Math.max(filters.minPrice, filters.maxPrice)
    const minArea = Math.min(filters.minArea, filters.maxArea)
    const maxArea = Math.max(filters.minArea, filters.maxArea)
    return availableListings.filter((listing) => {
      if (filters.rentalMode && listing.rentalMode !== filters.rentalMode) return false
      if (listing.price < minPrice || listing.price > maxPrice) return false
      if (listing.roomSizeM2 < minArea || listing.roomSizeM2 > maxArea) return false
      if (filters.roomTypes.length && !filters.roomTypes.includes(listing.roomType)) return false
      if (filters.roomCounts.length && !filters.roomCounts.includes(listing.roomCapacity)) return false
      return true
    })
  }, [availableListings, filters])

  const listings = useMemo(() => [...filteredListings].sort((a, b) => {
    if (order === 'cheap') return a.price - b.price
    if (order === 'expensive') return b.price - a.price
    if (order === 'saved-new') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || +new Date(b.publishedAt) - +new Date(a.publishedAt)
    if (order === 'saved-old') return Number(favorites.has(b.id)) - Number(favorites.has(a.id)) || +new Date(a.publishedAt) - +new Date(b.publishedAt)
    if (order === 'reduced') return a.price - b.price || b.views - a.views
    if (order === 'sqm-cheap') return a.price / Math.max(1, a.roomSizeM2) - b.price / Math.max(1, b.roomSizeM2)
    if (order === 'sqm-expensive') return b.price / Math.max(1, b.roomSizeM2) - a.price / Math.max(1, a.roomSizeM2)
    if (order === 'area-large') return b.roomSizeM2 - a.roomSizeM2
    if (order === 'area-small') return a.roomSizeM2 - b.roomSizeM2
    if (order === 'floor-high') return stableFloor(b) - stableFloor(a)
    if (order === 'floor-low') return stableFloor(a) - stableFloor(b)
    return +new Date(b.publishedAt) - +new Date(a.publishedAt)
  }), [favorites, filteredListings, order])

  if (!open) return null
  const t = resultsCopy[language] as ResultsCopy
  const contact = () => {
    if (currentUser) return
    setOpen(false); requestAnimationFrame(() => requestAnimationFrame(openExistingAuthentication))
  }
  const openMap = async () => {
    setOpen(false)
    if (document.querySelector('.m2-map-screen')) return
    document.querySelector<HTMLButtonElement>('.m2-select-row')?.click()
    ;(await waitForElement('[data-testid="search-map"]'))?.click()
  }
  const chooseRentalMode = (mode: RentalMode) => {
    setFilters((current) => ({ ...current, rentalMode: mode }))
    setRentalMode(mode)
    syncHomeRentalMode(mode)
  }
  const clearFilters = () => setFilters((current) => createDefaultFilters(current.rentalMode))

  return createPortal(<section className="m2-results notranslate" translate="no" data-testid="mobile-results">
    {panel === 'results' ? <><header className="m2-results__header"><button type="button" onClick={() => setOpen(false)} aria-label={t.back}><ChevronLeft /></button><div><strong>{t.header(listings.length)}</strong><small>{t.zone}</small></div></header>
      <div className="m2-results__toolbar"><button type="button" onClick={() => setPanel('filters')}><SlidersHorizontal />{t.filters}</button><button type="button" onClick={() => setPanel('sort')}><ArrowDownUp />{t.order}</button><button type="button" onClick={openMap}><Map />{t.map}</button></div>
      <div className="m2-results__summary"><span>{t.showing(listings.length, availableListings.length)}</span><b>{orderLabel(t, order)}</b></div><div className="m2-results__list">{listings.length ? listings.map((listing, index) => <MobileResultCard key={listing.id} listing={listing} index={index} language={language} favorite={favorites.has(listing.id)} onFavorite={() => toggleFavorite(listing.id)} onDiscard={() => discardListing(listing.id)} onContact={contact} />) : <div className="m2-results__empty">{t.empty}</div>}</div></> : null}

    {panel === 'sort' ? <section className="m2-results-panel"><header><button type="button" onClick={() => setPanel('results')} aria-label={t.close}><X /></button><strong>{t.order}</strong></header><div className="m2-results-sort" role="radiogroup">{orderKeys.map((value) => <button key={value} type="button" role="radio" aria-checked={order === value} onClick={() => { setOrder(value); setPanel('results') }}><span>{orderLabel(t, value)}</span><i>{order === value ? '●' : ''}</i></button>)}</div></section> : null}

    {panel === 'filters' ? <section className="m2-results-panel m2-results-filter"><header><button type="button" onClick={() => setPanel('results')} aria-label={t.close}><X /></button><strong>{t.filters}</strong><button type="button" className="m2-results-filter__clear" onClick={clearFilters}>{t.clear}</button></header><div className="m2-results-filter__scroll">
      <div className="m2-results-filter__transaction" role="group" aria-label={`${t.vivienda} / ${t.turismo}`}><button type="button" className={cn(filters.rentalMode === 'long' && 'is-active')} aria-pressed={filters.rentalMode === 'long'} onClick={() => chooseRentalMode('long')}>{t.vivienda}</button><button type="button" className={cn(filters.rentalMode === 'holiday' && 'is-active')} aria-pressed={filters.rentalMode === 'holiday'} onClick={() => chooseRentalMode('holiday')}>{t.turismo}</button></div>
      <label className="m2-results-filter__select"><span>{t.propertyType}</span><select value="residential" aria-label={t.propertyType} onChange={() => undefined}><option value="residential">{t.residential}</option></select><ChevronDown /></label>
      <fieldset><legend>{t.price}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.price} ${t.min}`} type="number" min="0" step="25" value={filters.minPrice} onChange={(event) => setFilters((current) => ({ ...current, minPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.price} ${t.max}`} type="number" min="0" step="25" value={filters.maxPrice} onChange={(event) => setFilters((current) => ({ ...current, maxPrice: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.area}</legend><div className="m2-results-filter__pair"><label><span>{t.min}</span><input aria-label={`${t.area} ${t.min}`} type="number" min="0" value={filters.minArea} onChange={(event) => setFilters((current) => ({ ...current, minArea: Math.max(0, Number(event.target.value) || 0) }))} /></label><label><span>{t.max}</span><input aria-label={`${t.area} ${t.max}`} type="number" min="0" value={filters.maxArea} onChange={(event) => setFilters((current) => ({ ...current, maxArea: Math.max(0, Number(event.target.value) || 0) }))} /></label></div></fieldset>
      <fieldset><legend>{t.rooms}</legend><div className="m2-results-filter__checks">{[[1, t.oneRoom], [2, t.twoRooms]].map(([value, label]) => <label key={String(value)}><input type="checkbox" checked={filters.roomCounts.includes(value as number)} onChange={() => setFilters((current) => ({ ...current, roomCounts: toggleValue(current.roomCounts, value as number) }))} /><span>{label}</span></label>)}</div></fieldset>
      <fieldset><legend>{t.housingType}</legend><div className="m2-results-filter__checks">{([['Habitación individual', t.individual], ['Habitación compartida', t.shared], ['Estudio', t.studio]] as const).map(([value, label]) => <label key={value}><input type="checkbox" checked={filters.roomTypes.includes(value)} onChange={() => setFilters((current) => ({ ...current, roomTypes: toggleValue(current.roomTypes, value) }))} /><span>{label}</span></label>)}</div></fieldset>
    </div><footer><button type="button" onClick={() => setPanel('results')}>{t.showListings} · {listings.length}</button></footer></section> : null}
  </section>, document.body)
}
