import { useEffect, useMemo, useRef } from 'react'
import { ChevronLeft, ChevronRight, Heart, MessageSquare, Phone, X } from 'lucide-react'
import { Link } from 'react-router'
import { MediaImage } from '@/components/media-image'
import { useApp } from '@/contexts/app-context'
import { getCriticalRestrictions, getPrimaryCadence, unknownListingFact } from '@/lib/listings'
import { priceLabel } from '@/components/map/map-icons'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'

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
  const saved = favorites.has(listing.id)
  const carousel = useMemo(() => siblingListings.length > 1 ? siblingListings : [listing], [listing, siblingListings])
  const carouselIndex = Math.max(0, carousel.findIndex((item) => item.id === listing.id))
  const hasCarousel = carousel.length > 1
  const previous = hasCarousel ? carousel[(carouselIndex - 1 + carousel.length) % carousel.length] : null
  const next = hasCarousel ? carousel[(carouselIndex + 1) % carousel.length] : null

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

  return <article
    ref={sheetRef}
    className="selected-listing-sheet map-selected-card"
    aria-label={`Habitación seleccionada en ${listing.area}`}
    tabIndex={-1}
    data-listing-id={listing.id}
    data-group-size={carousel.length}
    data-promoted={listing.promoted || undefined}
  >
    <div className={cn("selected-listing-sheet__media map-selected-card__media", hasCarousel && "has-neighbor-peeks")}>
      {previous ? <button type="button" className="selected-listing-sheet__neighbor-peek selected-listing-sheet__neighbor-peek--prev" aria-label="Ver anuncio anterior en esta dirección" onClick={() => onSelectSibling?.(previous.id)}><MediaImage src={previous.images[0]} variant="thumb" alt="" /></button> : null}
      {next ? <button type="button" className="selected-listing-sheet__neighbor-peek selected-listing-sheet__neighbor-peek--next" aria-label="Ver siguiente anuncio en esta dirección" onClick={() => onSelectSibling?.(next.id)}><MediaImage src={next.images[0]} variant="thumb" alt="" /></button> : null}
      <MediaImage className="selected-listing-sheet__primary-photo" src={listing.images[0]} variant="card" alt={`Habitación en ${listing.area}`} width="576" height="360" />
      {listing.images[1] ? <MediaImage className="selected-listing-sheet__secondary-photo" src={listing.images[1]} variant="thumb" alt="" width="384" height="360" /> : null}
      {listing.promoted ? <span className="selected-listing-sheet__promoted" aria-label="Anuncio TOP">👍</span> : null}
      {hasCarousel ? <>
        <button type="button" className="selected-listing-sheet__carousel-arrow selected-listing-sheet__carousel-arrow--prev" aria-label="Anuncio anterior en esta dirección" disabled={!previous} onClick={() => previous && onSelectSibling?.(previous.id)}><ChevronLeft aria-hidden="true" /></button>
        <button type="button" className="selected-listing-sheet__carousel-arrow selected-listing-sheet__carousel-arrow--next" aria-label="Siguiente anuncio en esta dirección" disabled={!next} onClick={() => next && onSelectSibling?.(next.id)}><ChevronRight aria-hidden="true" /></button>
        <span className="selected-listing-sheet__carousel-count" aria-label={`Anuncio ${carouselIndex + 1} de ${carousel.length} en esta dirección`}>${carouselIndex + 1}/${carousel.length}</span>
      </> : null}
      <span className="selected-listing-sheet__photo-count">1/{listing.images.length}</span>
    </div>
    <div className="selected-listing-sheet__content">
      {listing.isExternal && listing.sourceUrl ? <a href={listing.sourceUrl} target="_blank" rel="noopener noreferrer">{listing.title}</a> : <Link to={`/habitacion/${listing.id}`}>{listing.title}</Link>}
      <strong>{priceLabel(listing)} {listing.sourcePriceText ? null : <span>/{getPrimaryCadence(listing)}</span>}</strong>
      <p>{listing.approximateAddress ? `${listing.approximateAddress}, ${listing.city}` : `${listing.area}, ${listing.city}`}</p>
      <p className="selected-listing-sheet__facts">{listing.roomType} · {listing.currentResidents} residentes · {listing.roomSizeM2 == null ? unknownListingFact : `${listing.roomSizeM2} m²`}</p>
      <ul>{getCriticalRestrictions(listing).slice(0, 2).map((restriction) => <li key={restriction}>{restriction}</li>)}</ul>
    </div>
    <div className="selected-listing-sheet__actions">
      {listing.isExternal && listing.sourceUrl ? <a href={listing.sourceUrl} target="_blank" rel="noopener noreferrer"><MessageSquare aria-hidden="true" /><span>Ver anuncio</span></a> : <Link to={`/habitacion/${listing.id}#contacto`}><MessageSquare aria-hidden="true" /><span>Contactar</span></Link>}
      {listing.showPhone && listing.contactPhone ? <a href={`tel:${listing.contactPhone.replace(/\s+/g, '')}`}><Phone aria-hidden="true" /><span>Llamar</span></a> : null}
      <button type="button" className={cn('selected-listing-sheet__favorite', saved && 'is-saved')} aria-label={saved ? `Quitar ${listing.title} de favoritos` : `Guardar ${listing.title} en favoritos`} aria-pressed={saved} onClick={() => toggleFavorite(listing.id)}><Heart aria-hidden="true" fill={saved ? 'currentColor' : 'none'} /><span>Guardar</span></button>
    </div>
    <button type="button" className="selected-listing-sheet__close" aria-label="Cerrar vista previa" onClick={onClose}><X aria-hidden="true" /></button>
  </article>
}
