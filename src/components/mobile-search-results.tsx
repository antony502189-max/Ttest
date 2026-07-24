import { useEffect, useMemo, useState, type SyntheticEvent } from 'react'
import { createPortal } from 'react-dom'
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
} from 'lucide-react'
import { MediaImage } from '@/components/media-image'
import { useApp } from '@/contexts/app-context'
import type { Listing, RentalMode } from '@/types'
import { cn } from '@/lib/utils'
import '@/mobile-search-results.css'

type ResultsLanguage = 'es' | 'en' | 'ru'
type ResultsOrder = 'relevance' | 'price-asc' | 'price-desc'
type ResultsMode = 'all' | RentalMode

const resultsCopy = {
  es: {
    header: (count: number) => `${count} habitaciones en Tenerife`,
    zone: 'Tu zona seleccionada',
    filters: 'Filtros', order: 'Orden', map: 'Mapa', showing: (count: number) => `Viendo ${count} de ${count} habitaciones`, top: 'Destacado',
    contact: 'Contactar', call: 'Llamar', favorite: 'Guardar en favoritos', unfavorite: 'Quitar de favoritos', photo: 'Siguiente foto',
    all: 'Todas', housing: 'Vivienda', tourism: 'Turismo', closeFilters: 'Cerrar filtros',
    relevance: 'Relevancia', priceAsc: 'Precio más bajo', priceDesc: 'Precio más alto',
    residents: 'residentes', available: 'Disponible', back: 'Volver',
  },
  en: {
    header: (count: number) => `${count} rooms in Tenerife`,
    zone: 'Your selected area',
    filters: 'Filters', order: 'Order', map: 'Map', showing: (count: number) => `Viewing ${count} of ${count} rooms`, top: 'Featured',
    contact: 'Contact', call: 'Call', favorite: 'Add to favorites', unfavorite: 'Remove from favorites', photo: 'Next photo',
    all: 'All', housing: 'Housing', tourism: 'Tourism', closeFilters: 'Close filters',
    relevance: 'Relevance', priceAsc: 'Lowest price', priceDesc: 'Highest price',
    residents: 'residents', available: 'Available', back: 'Back',
  },
  ru: {
    header: (count: number) => `${count} объявлений на Тенерифе`,
    zone: 'Выбранная вами зона',
    filters: 'Фильтры', order: 'Порядок', map: 'Карта', showing: (count: number) => `Просмотрено ${count} из ${count} объявлений`, top: 'Топ',
    contact: 'Связаться', call: 'Позвонить', favorite: 'Добавить в избранное', unfavorite: 'Убрать из избранного', photo: 'Следующая фотография',
    all: 'Все', housing: 'Жильё', tourism: 'Туризм', closeFilters: 'Закрыть фильтры',
    relevance: 'По релевантности', priceAsc: 'Сначала дешевле', priceDesc: 'Сначала дороже',
    residents: 'жильцов', available: 'Доступно', back: 'Назад',
  },
} as const

const fallbackImage = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23282828"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%235d655f"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23727b74"/%3E%3C/svg%3E'

function currentLanguage(): ResultsLanguage {
  const language = document.documentElement.lang
  return language === 'en' || language === 'ru' ? language : 'es'
}

function isResultsTrigger(target: Element) {
  const toolbarButton = target.closest<HTMLButtonElement>('.m2-map-toolbar button')
  if (!toolbarButton || !toolbarButton.parentElement) return false
  const buttons = Array.from(toolbarButton.parentElement.querySelectorAll(':scope > button'))
  return buttons.indexOf(toolbarButton) === 1
}

function openExistingAuthentication() {
  const openMenuLogin = () => document.querySelector<HTMLButtonElement>('.m2-menu > .m2-primary')?.click()
  const menuScreen = document.querySelector('.m2-menu')
  if (menuScreen) {
    requestAnimationFrame(openMenuLogin)
    return
  }
  document.querySelector<HTMLButtonElement>('.m2-bottom-nav button:last-child')?.click()
  requestAnimationFrame(() => requestAnimationFrame(openMenuLogin))
}

function imageFallback(event: SyntheticEvent<HTMLImageElement>) {
  event.currentTarget.src = fallbackImage
}

function formatPrice(listing: Listing, language: ResultsLanguage) {
  const value = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES').format(listing.price)
  const cadence = listing.cadence === 'noche'
    ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche'
    : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'
  return `${value} € / ${cadence}`
}

function MobileResultCard({ listing, index, language, favorite, onFavorite, onContact }: {
  listing: Listing
  index: number
  language: ResultsLanguage
  favorite: boolean
  onFavorite: () => void
  onContact: () => void
}) {
  const t = resultsCopy[language]
  const [imageIndex, setImageIndex] = useState(0)
  const images = listing.images.length ? listing.images : [fallbackImage]
  const nextImage = () => setImageIndex((current) => (current + 1) % images.length)

  return <article className="m2-result-card" data-listing-id={listing.id}>
    <div className="m2-result-card__media">
      <button type="button" className="m2-result-card__image-button" onClick={nextImage} aria-label={`${t.photo}: ${listing.title}`}>
        <MediaImage src={images[imageIndex]} onError={imageFallback} alt={`${listing.title}, ${imageIndex + 1}/${images.length}`} loading="lazy" />
      </button>
      {index < 2 ? <span className="m2-result-card__top">{t.top}</span> : null}
      <span className="m2-result-card__counter"><ImageIcon />{imageIndex + 1}/{images.length}</span>
      {images.length > 1 ? <button type="button" className="m2-result-card__next" onClick={nextImage} aria-label={t.photo}><ChevronRight /></button> : null}
    </div>

    <div className="m2-result-card__content">
      <p className="m2-result-card__location"><MapPin />{listing.area}, {listing.city}</p>
      <h2>{listing.title}</h2>
      <strong className="m2-result-card__price">{formatPrice(listing, language)}</strong>
      <p className="m2-result-card__facts">{listing.roomType} · {listing.roomSizeM2} m² · {listing.currentResidents} {t.residents}</p>
      <p className="m2-result-card__availability">{listing.available}</p>
      <div className="m2-result-card__badges">
        {listing.restrictions.slice(0, 2).map((restriction) => <span key={restriction}>{restriction}</span>)}
      </div>
      <div className="m2-result-card__actions">
        <button type="button" onClick={onContact}><MessageCircle />{t.contact}</button>
        {listing.showPhone && listing.contactPhone ? <a href={`tel:${listing.contactPhone}`}><Phone />{t.call}</a> : null}
        <button type="button" className={cn('m2-result-card__favorite', favorite && 'is-active')} onClick={onFavorite} aria-label={favorite ? t.unfavorite : t.favorite} aria-pressed={favorite}><Heart /></button>
      </div>
    </div>
  </article>
}

export function MobileSearchResults() {
  const { allListings, discarded, favorites, toggleFavorite, currentUser } = useApp()
  const [open, setOpen] = useState(false)
  const [language, setLanguage] = useState<ResultsLanguage>('es')
  const [mode, setMode] = useState<ResultsMode>('all')
  const [order, setOrder] = useState<ResultsOrder>('relevance')
  const [filtersOpen, setFiltersOpen] = useState(false)

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element) || !isResultsTrigger(target)) return
      event.preventDefault()
      event.stopPropagation()
      setLanguage(currentLanguage())
      setOpen(true)
    }
    document.addEventListener('click', handleClick, true)
    return () => document.removeEventListener('click', handleClick, true)
  }, [])

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const listings = useMemo(() => {
    const visible = allListings.filter((listing) => listing.status === 'Publicado' && !discarded.has(listing.id) && (mode === 'all' || listing.rentalMode === mode))
    if (order === 'price-asc') return [...visible].sort((a, b) => a.price - b.price)
    if (order === 'price-desc') return [...visible].sort((a, b) => b.price - a.price)
    return visible
  }, [allListings, discarded, mode, order])

  if (!open) return null
  const t = resultsCopy[language]
  const orderLabel = order === 'price-asc' ? t.priceAsc : order === 'price-desc' ? t.priceDesc : t.relevance
  const cycleOrder = () => setOrder((current) => current === 'relevance' ? 'price-asc' : current === 'price-asc' ? 'price-desc' : 'relevance')
  const contact = () => {
    if (currentUser) return
    setOpen(false)
    requestAnimationFrame(() => requestAnimationFrame(openExistingAuthentication))
  }

  return createPortal(<section className="m2-results notranslate" translate="no" data-testid="mobile-results">
    <header className="m2-results__header">
      <button type="button" onClick={() => setOpen(false)} aria-label={t.back}><ChevronLeft /></button>
      <div><strong>{t.header(listings.length)}</strong><small>{t.zone}</small></div>
    </header>

    <div className="m2-results__toolbar">
      <button type="button" className={cn(filtersOpen && 'is-active')} onClick={() => setFiltersOpen((value) => !value)} aria-expanded={filtersOpen}><SlidersHorizontal />{t.filters}</button>
      <button type="button" onClick={cycleOrder} title={orderLabel}><ArrowDownUp />{t.order}</button>
      <button type="button" onClick={() => setOpen(false)}><Map />{t.map}</button>
    </div>

    {filtersOpen ? <div className="m2-results__filters" role="group" aria-label={t.filters}>
      {([['all', t.all], ['long', t.housing], ['holiday', t.tourism]] as const).map(([value, label]) => <button key={value} type="button" className={cn(mode === value && 'is-active')} onClick={() => setMode(value)} aria-pressed={mode === value}>{label}</button>)}
    </div> : null}

    <div className="m2-results__summary"><span>{t.showing(listings.length)}</span><b>{orderLabel}</b></div>
    <div className="m2-results__list">
      {listings.map((listing, index) => <MobileResultCard key={listing.id} listing={listing} index={index} language={language} favorite={favorites.has(listing.id)} onFavorite={() => toggleFavorite(listing.id)} onContact={contact} />)}
    </div>
  </section>, document.body)
}
