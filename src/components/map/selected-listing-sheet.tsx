import { useEffect, useMemo, useRef } from 'react'
import { ChevronLeft, ChevronRight, Heart, MessageSquare, Phone, X } from 'lucide-react'
import { Link } from 'react-router'
import { MediaImage } from '@/components/media-image'
import { useApp } from '@/contexts/app-context'
import { getCriticalRestrictions, getPrimaryCadence, unknownListingFact } from '@/lib/listings'
import { priceLabel } from '@/components/map/map-icons'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'

type CarouselPosition = 'previous' | 'current' | 'next'

export function SelectedListingSheet({
  listing,
  siblingListings = [],
  onSelectSibling,
  onClose,
  focusOnOpen = false,
  returnFocus,
}: {
  listing: Listing
  siblingListings?: Listing[]
  onSelectSibling?: (id: string) => void
  onClose: () => void
  focusOnOpen?: boolean
  returnFocus?: HTMLElement | null
}) {
  const { favorites, toggleFavorite } = useApp()
  const sheetRef = useRef<HTMLElement>(null)
  const carousel = useMemo(() => siblingListings.length > 1 ? siblingListings : [listing], [listing, siblingListings])
  const carouselIndex = Math.max(0, carousel.findIndex((item) => item.id === listing.id))
  const hasCarousel = carousel.length > 1
  const previous = hasCarousel ? carousel[(carouselIndex - 1 + carousel.length) % carousel.length] : null
  const next = hasCarousel ? carousel[(carouselIndex + 1) % carousel.length] : null

  const slots = useMemo<Array<{ item: Listing; position: CarouselPosition }>>(() => {
    if (!hasCarousel) return [{ item: listing, position: 'current' }]
    if (carousel.length === 2) {
      return [
        { item: listing, position: 'current' },
        { item: next!, position: 'next' },
      ]
    }
    return [
      { item: previous!, position: 'previous' },
      { item: listing, position: 'current' },
      { item: next!, position: 'next' },
    ]
  }, [carousel.length, hasCarousel, listing, next, previous])

  useEffect(() => {
    if (focusOnOpen) requestAnimationFrame(() => sheetRef.current?.focus())
  }, [focusOnOpen, listing.id])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      onClose()
      requestAnimationFrame(() => returnFocus?.focus())
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, returnFocus])

  const selectSibling = (item: Listing | null) => {
    if (item) onSelectSibling?.(item.id)
  }

  const renderCard = ({ item, position }: { item: Listing; position: CarouselPosition }) => {
    const current = position === 'current'
    const saved = favorites.has(item.id)
    return <article
      key={item.id}
      ref={current ? sheetRef : undefined}
      className={cn('selected-listing-sheet map-selected-card selected-listing-carousel__card', `is-${position}`)}
      aria-label={current ? `Habitación seleccionada en ${item.area}` : undefined}
      aria-hidden={current ? undefined : true}
      tabIndex={current ? -1 : undefined}
      data-listing-id={item.id}
      data-carousel-position={position}
      data-promoted={item.promoted || undefined}
    >
      <div className="selected-listing-sheet__media map-selected-card__media">
        <MediaImage className="selected-listing-sheet__primary-photo" src={item.images[0]} variant="card" alt={current ? `Habitación en ${item.area}` : ''} width="576" height="360" />
        {item.promoted ? <span className="selected-listing-sheet__promoted" aria-label="Anuncio TOP">👍</span> : null}
        <span className="selected-listing-sheet__photo-count">1/{item.images.length}</span>
      </div>
      <div className="selected-listing-sheet__content">
        {current
          ? item.isExternal && item.sourceUrl
            ? <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer">{item.title}</a>
            : <Link to={`/habitacion/${item.id}`}>{item.title}</Link>
          : <span className="selected-listing-carousel__title-preview">{item.title}</span>}
        <strong>{priceLabel(item)} {item.sourcePriceText ? null : <span>/{getPrimaryCadence(item)}</span>}</strong>
        <p>{item.approximateAddress ? `${item.approximateAddress}, ${item.city}` : `${item.area}, ${item.city}`}</p>
        <p className="selected-listing-sheet__facts">{item.roomType} · {item.currentResidents} residentes · {item.roomSizeM2 == null ? unknownListingFact : `${item.roomSizeM2} m²`}</p>
        <ul>{getCriticalRestrictions(item).slice(0, 2).map((restriction) => <li key={restriction}>{restriction}</li>)}</ul>
      </div>
      <div className="selected-listing-sheet__actions">
        {current ? <>
          {item.isExternal && item.sourceUrl ? <a href={item.sourceUrl} target="_blank" rel="noopener noreferrer"><MessageSquare aria-hidden="true" /><span>Ver anuncio</span></a> : <Link to={`/habitacion/${item.id}#contacto`}><MessageSquare aria-hidden="true" /><span>Contactar</span></Link>}
          {item.showPhone && item.contactPhone ? <a href={`tel:${item.contactPhone.replace(/\s+/g, '')}`}><Phone aria-hidden="true" /><span>Llamar</span></a> : null}
          <button type="button" className={cn('selected-listing-sheet__favorite', saved && 'is-saved')} aria-label={saved ? `Quitar ${item.title} de favoritos` : `Guardar ${item.title} en favoritos`} aria-pressed={saved} onClick={() => toggleFavorite(item.id)}><Heart aria-hidden="true" fill={saved ? 'currentColor' : 'none'} /><span>Guardar</span></button>
        </> : <>
          <span className="selected-listing-carousel__action-preview"><MessageSquare aria-hidden="true" /></span>
          {item.showPhone && item.contactPhone ? <span className="selected-listing-carousel__action-preview"><Phone aria-hidden="true" /></span> : null}
          <span className={cn('selected-listing-carousel__action-preview', saved && 'is-saved')}><Heart aria-hidden="true" fill={saved ? 'currentColor' : 'none'} /></span>
        </>}
      </div>
      {current ? <button type="button" className="selected-listing-sheet__close" aria-label="Cerrar vista previa" onClick={onClose}><X aria-hidden="true" /></button> : null}
      {!current ? <button
        type="button"
        className="selected-listing-carousel__side-hit"
        tabIndex={-1}
        aria-hidden="true"
        onClick={() => selectSibling(item)}
      /> : null}
    </article>
  }

  return <section
    className={cn('selected-listing-carousel', hasCarousel && 'has-multiple', carousel.length === 2 && 'has-two')}
    data-testid="desktop-same-address-carousel"
    data-listing-id={listing.id}
    data-group-size={carousel.length}
  >
    <div className="selected-listing-carousel__stage">
      {slots.map(renderCard)}
    </div>
    {hasCarousel ? <>
      <button type="button" className="selected-listing-carousel__arrow selected-listing-carousel__arrow--prev" aria-label="Anuncio anterior en esta dirección" onClick={() => selectSibling(previous)}><ChevronLeft aria-hidden="true" /></button>
      <button type="button" className="selected-listing-carousel__arrow selected-listing-carousel__arrow--next" aria-label="Siguiente anuncio en esta dirección" onClick={() => selectSibling(next)}><ChevronRight aria-hidden="true" /></button>
      <span className="selected-listing-carousel__count" aria-label={`Anuncio ${carouselIndex + 1} de ${carousel.length} en esta dirección`}>{carouselIndex + 1}/{carousel.length}</span>
    </> : null}
  </section>
}
