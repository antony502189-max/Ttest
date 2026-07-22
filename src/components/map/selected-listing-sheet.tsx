import { useEffect, useRef } from 'react'
import { Heart, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { MediaImage } from '@/components/media-image'
import { useApp } from '@/contexts/app-context'
import { getCriticalRestrictions, getPrimaryCadence } from '@/lib/listings'
import { priceLabel } from '@/components/map/map-icons'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'

export function SelectedListingSheet({ listing, onClose, focusOnOpen = false, returnFocus }: { listing: Listing; onClose: () => void; focusOnOpen?: boolean; returnFocus?: HTMLElement | null }) {
  const { favorites, toggleFavorite } = useApp()
  const sheetRef = useRef<HTMLElement>(null)
  const saved = favorites.has(listing.id)

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

  return <article ref={sheetRef} className="selected-listing-sheet map-selected-card" aria-label={`Habitación seleccionada en ${listing.area}`} tabIndex={-1}>
    <div className="selected-listing-sheet__media"><MediaImage src={listing.images[0]} alt={`Habitación en ${listing.area}`} width="288" height="216" /></div>
    <div className="selected-listing-sheet__content">
      <p>{listing.area}, {listing.city}</p>
      <strong>{priceLabel(listing)} <span>/{getPrimaryCadence(listing)}</span></strong>
      <Link to={`/habitacion/${listing.id}`}>{listing.title}</Link>
      <ul>{getCriticalRestrictions(listing).slice(0, 2).map((restriction) => <li key={restriction}>{restriction}</li>)}</ul>
    </div>
    <div className="selected-listing-sheet__actions">
      <button type="button" className={cn('selected-listing-sheet__favorite', saved && 'is-saved')} aria-label={saved ? `Quitar ${listing.title} de favoritos` : `Guardar ${listing.title} en favoritos`} aria-pressed={saved} onClick={() => toggleFavorite(listing.id)}><Heart aria-hidden="true" fill={saved ? 'currentColor' : 'none'} /></button>
      <button type="button" aria-label="Cerrar vista previa" onClick={onClose}><X aria-hidden="true" /></button>
    </div>
  </article>
}
