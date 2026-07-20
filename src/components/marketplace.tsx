import { lazy, Suspense, useEffect, useId, useMemo, useState, type FormEvent, type ReactNode, type SyntheticEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bath, BedDouble, CalendarDays, Camera, ChevronLeft, ChevronRight, CigaretteOff, CircleAlert, Euro, Expand, Heart, Home, MapPin, MessageCircle, PawPrint, Phone, Search, Share2, ShieldCheck, SlidersHorizontal, Sparkles, Trash2, UsersRound } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Slider } from '@/components/ui/slider'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { amenityOptions, areas, defaultFilters, initialListings } from '@/data/listings'
import { filterListings, filtersToParams, formatPublishedAt } from '@/lib/search'
import type { Filters, Listing, MapPolygonPoint, RentalMode, YesNoAny } from '@/types'
import { useApp } from '@/contexts/app-context'

const LazyLeafletMap = lazy(() => import('@/components/map-view').then((module) => ({ default: module.LeafletMapView })))
export type { MapBounds } from '@/components/map-view'

const fallbackImage = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23eceeea"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%2398a19a"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23b7beb8"/%3E%3Ctext x="400" y="445" text-anchor="middle" fill="%235b635d" font-family="Arial" font-size="28"%3EFoto no disponible%3C/text%3E%3C/svg%3E'
const imageFallback = (event: SyntheticEvent<HTMLImageElement>) => { event.currentTarget.src = fallbackImage }

export function RentalTypeSwitch({ compact = false }: { compact?: boolean }) {
  const { rentalMode, setRentalMode } = useApp()
  return <ToggleGroup type="single" value={rentalMode} onValueChange={(value) => { if (value) setRentalMode(value as RentalMode) }} className={cn('rental-switch', compact && 'rental-switch--compact')} aria-label="Tipo de alquiler">
    <ToggleGroupItem value="long">Larga estancia</ToggleGroupItem>
    <ToggleGroupItem value="holiday">Alquiler vacacional</ToggleGroupItem>
  </ToggleGroup>
}

export function SearchLocationInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  const listId = useId()
  const { searchHistory, filters, setFilters } = useApp()
  const suggestions = [...new Set([...searchHistory, 'Tenerife', ...areas])]
  return <div className="search-location"><label htmlFor={id}>Ciudad, barrio o zona</label><div><MapPin aria-hidden="true" /><Input id={id} list={listId} value={value} onChange={(event) => onChange(event.target.value)} placeholder="Ej. Los Cristianos" /><datalist id={listId}>{suggestions.map((suggestion) => <option key={suggestion} value={suggestion} />)}</datalist><LocationSelector selected={filters.areas} onApply={(selected) => { setFilters({ ...filters, areas: selected }); onChange(selected.length === 1 ? selected[0] : 'Tenerife') }} /></div></div>
}

export function SearchBar({ compact = false }: { compact?: boolean }) {
  const { query, setQuery, addSearchHistory, filters, setFilters, rentalMode } = useApp()
  const navigate = useNavigate()
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const normalized = query.trim() || 'Tenerife'
    const exactArea = areas.find((area) => area.toLocaleLowerCase() === normalized.toLocaleLowerCase())
    const nextFilters = { ...filters, areas: exactArea ? [exactArea] : filters.areas }
    setFilters(nextFilters)
    addSearchHistory(normalized)
    const params = filtersToParams(nextFilters, new URLSearchParams({ q: normalized, alquiler: rentalMode }))
    navigate(`/buscar?${params.toString()}`)
  }
  return <form className={cn('search-bar', compact && 'search-bar--compact')} onSubmit={submit} role="search"><SearchLocationInput value={query} onChange={setQuery} />{compact ? null : <div className="search-date"><label htmlFor="move-date">Entrada</label><div><CalendarDays aria-hidden="true" /><Input id="move-date" type="date" value={filters.available} onChange={(event) => setFilters({ ...filters, available: event.target.value })} /></div></div>}<Button size="lg" type="submit"><Search data-icon="inline-start" />Buscar</Button></form>
}

export function LocationSelector({ selected, onApply }: { selected: string[]; onApply: (selectedAreas: string[]) => void }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(selected)
  const [term, setTerm] = useState('')
  const filteredAreas = areas.filter((area) => area.toLocaleLowerCase().includes(term.trim().toLocaleLowerCase()))
  useEffect(() => { if (open) setDraft(selected) }, [open, selected])
  const toggle = (area: string) => setDraft((current) => current.includes(area) ? current.filter((item) => item !== area) : [...current, area])
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button type="button" variant="ghost" size="sm" className="location-selector-trigger" aria-label={`Elegir zonas. ${selected.length || 'Ninguna'} seleccionadas`}><SlidersHorizontal data-icon="inline-start" /><span>Zonas{selected.length ? ` (${selected.length})` : ''}</span></Button></DialogTrigger><DialogContent className="location-selector-dialog"><DialogHeader><DialogTitle>¿Dónde quieres buscar?</DialogTitle><DialogDescription>Selecciona una o varias zonas de Tenerife.</DialogDescription></DialogHeader><label className="location-selector-search"><span className="sr-only">Buscar zona</span><Search aria-hidden="true" /><Input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Buscar municipio o barrio" autoComplete="off" /></label><div className="location-selector-summary"><strong>Tenerife</strong><button type="button" onClick={() => setDraft([])}>Toda la isla</button></div><div className="location-selector-list" role="group" aria-label="Zonas de Tenerife">{filteredAreas.map((area) => <label className="location-selector-option" key={area}><Checkbox checked={draft.includes(area)} onCheckedChange={() => toggle(area)} /><span><strong>{area}</strong><small>{initialListings.filter((listing) => listing.area === area).length} habitaciones demo</small></span></label>)}</div><DialogFooter className="location-selector-footer"><Button variant="ghost" onClick={() => setDraft([])}>Borrar</Button><Button onClick={() => { onApply(draft); setOpen(false) }}>Aplicar{draft.length ? ` ${draft.length} zonas` : ''}</Button></DialogFooter></DialogContent></Dialog>
}

const restrictionTone = (text: string) => text.includes('incluid') || text.includes('permitid') || text.includes('posible') ? 'positive' : text.includes('Solo') || text.includes('Sin') || text.includes('No ') ? 'restriction' : 'neutral'
const restrictionIcon = (text: string) => text.toLocaleLowerCase().includes('mascota') ? PawPrint : text.toLocaleLowerCase().includes('fumar') ? CigaretteOff : text.includes('mes') || text.includes('noche') ? CalendarDays : text.includes('Gastos') ? Euro : text.includes('Parej') || text.includes('hombre') || text.includes('mujer') || text.includes('género') ? UsersRound : ShieldCheck

export function PropertyBadge({ children }: { children: string }) {
  const Icon = restrictionIcon(children)
  return <Badge variant="outline" className={cn('property-badge', `property-badge--${restrictionTone(children)}`)}><Icon aria-hidden="true" />{children}</Badge>
}

export function FavoriteButton({ listing }: { listing: Listing }) {
  const { favorites, toggleFavorite } = useApp()
  const saved = favorites.has(listing.id)
  return <button type="button" className={cn('favorite-button', saved && 'is-saved')} aria-label={saved ? `Quitar ${listing.title} de favoritos` : `Guardar ${listing.title} en favoritos`} aria-pressed={saved} onClick={() => toggleFavorite(listing.id)}><Heart aria-hidden="true" fill={saved ? 'currentColor' : 'none'} /></button>
}

export function PriceBlock({ listing, large = false }: { listing: Listing; large?: boolean }) {
  return <div className={cn('price-block', large && 'price-block--large')}><strong>{new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(listing.price)}</strong><span>/{listing.cadence}</span></div>
}

export function PropertyCard({ listing, compact = false, selected = false, onFocus }: { listing: Listing; compact?: boolean; selected?: boolean; onFocus?: () => void }) {
  const { discardListing } = useApp()
  const [imageIndex, setImageIndex] = useState(0)
  const share = async () => {
    const url = `${location.origin}${location.pathname}#/habitacion/${listing.id}`
    if (navigator.share) await navigator.share({ title: listing.title, url }).catch(() => undefined)
    else await navigator.clipboard?.writeText(url).then(() => toast.success('Enlace copiado')).catch(() => toast.info(url))
  }
  const visibleRestrictions = listing.restrictions.slice(0, compact ? 2 : 3)
  return <article className={cn('property-card', compact && 'property-card--compact', selected && 'is-selected')} onMouseEnter={onFocus} onFocus={onFocus} data-listing-id={listing.id}>
    <div className="property-card__media"><Link to={`/habitacion/${listing.id}`} aria-label={`Ver ${listing.title}`}><img src={listing.images[imageIndex] || fallbackImage} onError={imageFallback} alt={`Habitación en ${listing.area}, foto ${imageIndex + 1} de ${listing.images.length}`} width="720" height="480" loading="lazy" /></Link><button type="button" className="card-gallery-arrow card-gallery-arrow--previous" onClick={() => setImageIndex((current) => (current - 1 + listing.images.length) % listing.images.length)} aria-label={`Foto anterior de ${listing.title}`}><ChevronLeft /></button><button type="button" className="card-gallery-arrow card-gallery-arrow--next" onClick={() => setImageIndex((current) => (current + 1) % listing.images.length)} aria-label={`Foto siguiente de ${listing.title}`}><ChevronRight /></button><span className="image-counter"><Camera aria-hidden="true" />{imageIndex + 1}/{listing.images.length}</span><FavoriteButton listing={listing} />{listing.advertiserType === 'Profesional' ? <span className="listing-status">Profesional</span> : null}</div>
    <div className="property-card__content"><h3><Link to={`/habitacion/${listing.id}`}>{listing.title}</Link></h3><div className="card-topline"><PriceBlock listing={listing} /><span>{listing.bills}</span></div><p className="property-location"><MapPin aria-hidden="true" />{listing.area}, {listing.city}</p><div className="property-facts"><span><BedDouble aria-hidden="true" />{listing.roomType}</span><span>{listing.occupants} residentes</span><span><CalendarDays aria-hidden="true" />{listing.available}</span></div>{compact ? null : <p className="property-description">{listing.description}</p>}<div className="badge-row">{visibleRestrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}{listing.restrictions.length > visibleRestrictions.length ? <Badge variant="secondary">+{listing.restrictions.length - visibleRestrictions.length} condiciones</Badge> : null}</div><div className="property-card__meta"><span>{formatPublishedAt(listing.publishedAt)}</span><span>{listing.advertiserType}</span></div>{compact ? null : <div className="property-card__actions"><Button asChild><Link to={`/habitacion/${listing.id}`}><MessageCircle data-icon="inline-start" />Contactar</Link></Button><Button variant="outline" onClick={() => toast.info(listing.contactPhone || '+34 600 112 233')}><Phone data-icon="inline-start" />Ver teléfono</Button><button type="button" className="card-text-action" onClick={() => { discardListing(listing.id); toast.success('Anuncio descartado de la búsqueda') }}><Trash2 aria-hidden="true" />Descartar</button><button type="button" className="card-text-action" onClick={share}><Share2 aria-hidden="true" />Compartir</button></div>}</div>
  </article>
}

export function LoadingSkeleton({ count = 3 }: { count?: number }) { return <div className="skeleton-list" aria-label="Cargando habitaciones" aria-busy="true">{Array.from({ length: count }).map((_, index) => <div className="property-skeleton" key={index}><Skeleton className="h-full min-h-52" /><div><Skeleton className="h-7 w-28" /><Skeleton className="h-5 w-4/5" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-16 w-full" /></div></div>)}</div> }
export function EmptyState({ favorites = false, onReset }: { favorites?: boolean; onReset?: () => void }) { return <Empty className="empty-state"><EmptyHeader><EmptyMedia variant="icon">{favorites ? <Heart /> : <Search />}</EmptyMedia><EmptyTitle>{favorites ? 'Aún no has guardado habitaciones' : 'No hay habitaciones con estos filtros'}</EmptyTitle><EmptyDescription>{favorites ? 'Guarda las que te gusten para compararlas aquí.' : 'Prueba a ampliar el precio, quitar una condición o recuperar anuncios descartados.'}</EmptyDescription></EmptyHeader><EmptyContent>{onReset ? <Button onClick={onReset}>Borrar filtros</Button> : <Button asChild><Link to="/buscar">Explorar habitaciones</Link></Button>}</EmptyContent></Empty> }
export function ErrorState() { return <Alert variant="destructive"><CircleAlert /><AlertTitle>No hemos podido cargar los resultados</AlertTitle><AlertDescription>Comprueba tu conexión y vuelve a intentarlo. Tus filtros siguen guardados. <Button variant="outline" size="sm" onClick={() => location.reload()}>Reintentar</Button></AlertDescription></Alert> }

const filterConditions = ['Parejas permitidas', 'Mascotas permitidas', 'No fumar', 'Empadronamiento posible', 'Gastos incluidos']
function CheckOption({ label, checked, onCheckedChange }: { label: string; checked: boolean; onCheckedChange: (checked: boolean) => void }) { const id = useId(); return <label className="check-option" htmlFor={id}><Checkbox id={id} checked={checked} onCheckedChange={(value) => onCheckedChange(value === true)} /><span>{label}</span></label> }
function NativeSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) { const id = useId(); return <label className="field-label" htmlFor={id}>{label}<select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => <option key={option}>{option}</option>)}</select></label> }
function YesNoFilter({ label, value, onChange }: { label: string; value: YesNoAny; onChange: (value: YesNoAny) => void }) { return <NativeSelect label={label} value={value} options={['Cualquiera', 'Sí', 'No']} onChange={(next) => onChange(next as YesNoAny)} /> }

function FilterPanel({ value, onChange, rentalMode }: { value: Filters; onChange: (value: Filters) => void; rentalMode: RentalMode }) {
  const update = <K extends keyof Filters>(key: K, next: Filters[K]) => onChange({ ...value, [key]: next })
  const max = rentalMode === 'holiday' ? 350 : 1200
  return <div className="filter-panel">
    <section className="filter-section"><h3>Precio por {rentalMode === 'holiday' ? 'noche' : 'mes'}</h3><div className="range-values"><span>{value.minPrice} €</span><span>{value.maxPrice >= max ? `${max} €+` : `${value.maxPrice} €`}</span></div><Slider min={0} max={max} step={rentalMode === 'holiday' ? 5 : 25} value={[Math.min(value.minPrice, max), Math.min(value.maxPrice, max)]} onValueChange={([min, nextMax]) => onChange({ ...value, minPrice: min, maxPrice: nextMax })} aria-label="Rango de precio" /></section><Separator />
    <fieldset className="filter-section"><legend>Zona</legend><div className="checks-grid">{areas.map((area) => <CheckOption key={area} label={area} checked={value.areas.includes(area)} onCheckedChange={(checked) => update('areas', checked ? [...value.areas, area] : value.areas.filter((item) => item !== area))} />)}</div></fieldset><Separator />
    <section className="filter-section"><h3>Habitación</h3><NativeSelect label="Tipo" value={value.roomType} options={['Cualquiera', 'Habitación individual', 'Habitación compartida', 'Estudio']} onChange={(next) => update('roomType', next)} /><NativeSelect label="Preferencia de ocupación" value={value.gender} options={['Cualquiera', 'Solo hombre', 'Solo mujer', 'Sin preferencia de género']} onChange={(next) => update('gender', next as Filters['gender'])} /></section><Separator />
    <section className="filter-section"><h3>Disponibilidad</h3><label className="field-label">Disponible para esta fecha<Input type="date" value={value.available} onChange={(event) => update('available', event.target.value)} /></label>{rentalMode === 'long' ? <NativeSelect label="Estancia máxima aceptada" value={value.minStay} options={['Cualquiera', '1', '2', '3', '6']} onChange={(next) => update('minStay', next)} /> : null}<NativeSelect label="Publicado" value={value.publicationDate} options={['Cualquiera', '24h', '7d', '30d']} onChange={(next) => update('publicationDate', next)} /></section><Separator />
    <fieldset className="filter-section"><legend>Condiciones destacadas</legend><div className="checks-grid">{filterConditions.map((condition) => <CheckOption key={condition} label={condition} checked={value.conditions.includes(condition)} onCheckedChange={(checked) => update('conditions', checked ? [...value.conditions, condition] : value.conditions.filter((item) => item !== condition))} />)}</div></fieldset><Separator />
    <section className="filter-section"><h3>Convivencia</h3><YesNoFilter label="Se puede fumar" value={value.smoking} onChange={(next) => update('smoking', next)} /><YesNoFilter label="Mascotas" value={value.pets} onChange={(next) => update('pets', next)} /><YesNoFilter label="Parejas" value={value.couples} onChange={(next) => update('couples', next)} /><YesNoFilter label="Niños" value={value.children} onChange={(next) => update('children', next)} /><YesNoFilter label="Empadronamiento" value={value.empadronamiento} onChange={(next) => update('empadronamiento', next)} /></section><Separator />
    <section className="filter-section"><h3>Espacios y equipamiento</h3><NativeSelect label="Baño" value={value.bathroom} options={['Cualquiera', 'Baño privado', 'Baño compartido']} onChange={(next) => update('bathroom', next)} /><NativeSelect label="Cocina" value={value.kitchen} options={['Cualquiera', 'Cocina privada', 'Cocina compartida']} onChange={(next) => update('kitchen', next)} /><CheckOption label="Amueblada" checked={value.furnished} onCheckedChange={(checked) => update('furnished', checked)} /><CheckOption label="Gastos incluidos" checked={value.billsIncluded} onCheckedChange={(checked) => update('billsIncluded', checked)} /><div className="checks-grid">{amenityOptions.map((amenity) => <CheckOption key={amenity} label={amenity} checked={value.amenities.includes(amenity)} onCheckedChange={(checked) => update('amenities', checked ? [...value.amenities, amenity] : value.amenities.filter((item) => item !== amenity))} />)}</div></section><Separator />
    <section className="filter-section"><h3>Fianza y vivienda</h3><NativeSelect label="Depósito" value={value.deposit} options={['Cualquiera', 'Sin fianza', 'Hasta 1 mes', 'Más de 1 mes']} onChange={(next) => update('deposit', next)} /><NativeSelect label="Personas en la vivienda" value={value.occupants} options={['Cualquiera', '1–2', '3–4', '5 o más']} onChange={(next) => update('occupants', next)} /><NativeSelect label="Tipo de anunciante" value={value.advertiserType} options={['Cualquiera', 'Particular', 'Profesional']} onChange={(next) => update('advertiserType', next)} /></section>
  </div>
}

export function FilterButton({ resultCount }: { resultCount: number }) {
  const { filters, setFilters, resetFilters, activeFilterCount, rentalMode, allListings, discarded } = useApp()
  const [draft, setDraft] = useState(filters)
  const [open, setOpen] = useState(false)
  const draftResultCount = useMemo(() => filterListings(allListings.filter((item) => !discarded.has(item.id)), rentalMode, draft).length, [allListings, discarded, draft, rentalMode])
  useEffect(() => { if (open) setDraft(filters) }, [open, filters])
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline" aria-label={`Todos los filtros. ${resultCount} habitaciones actuales`}><SlidersHorizontal data-icon="inline-start" />Filtros{activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}</Button></SheetTrigger><SheetContent className="filter-drawer"><SheetHeader><SheetTitle>Filtros</SheetTitle><SheetDescription>Todos los controles cambian el resultado y se guardan en la URL.</SheetDescription></SheetHeader><FilterPanel value={draft} onChange={setDraft} rentalMode={rentalMode} /><SheetFooter className="filter-footer"><Button variant="ghost" onClick={() => { setDraft({ ...defaultFilters }); resetFilters() }}>Limpiar</Button><Button onClick={() => { setFilters(draft); setOpen(false) }}>Mostrar {draftResultCount} habitaciones</Button></SheetFooter></SheetContent></Sheet>
}

export function FilterSidebar({ resultCount }: { resultCount: number }) {
  const { filters, setFilters, resetFilters, activeFilterCount, saveCurrentSearch, rentalMode } = useApp()
  return <aside className="filter-sidebar" aria-label="Filtros de búsqueda"><div className="filter-sidebar__save"><Button className="w-full" onClick={saveCurrentSearch}><Heart data-icon="inline-start" />Guardar búsqueda</Button><p>Recibe avisos cuando haya habitaciones nuevas.</p></div><div className="filter-sidebar__head"><h2>Filtrar resultados</h2>{activeFilterCount ? <button type="button" onClick={resetFilters}>Borrar ({activeFilterCount})</button> : null}</div><FilterPanel value={filters} onChange={setFilters} rentalMode={rentalMode} /><div className="filter-sidebar__result" aria-live="polite"><strong>{resultCount}</strong> habitaciones</div></aside>
}

export function MapView(props: { items: Listing[]; selectedId?: string; onSelect: (id: string) => void; fullScreen?: boolean; showPreview?: boolean; onBoundsSearch?: (bounds: import('@/components/map-view').MapBounds) => void; onPolygonSearch?: (polygon: MapPolygonPoint[]) => void }) {
  return <Suspense fallback={<div className="map-loading map-loading--standalone" role="status"><span aria-hidden="true" /><strong>Cargando mapa OpenStreetMap</strong></div>}><LazyLeafletMap {...props} /></Suspense>
}

export function PropertyGallery({ listing }: { listing: Listing }) {
  const [index, setIndex] = useState(0)
  const [open, setOpen] = useState(false)
  const next = () => setIndex((value) => (value + 1) % listing.images.length)
  const previous = () => setIndex((value) => (value - 1 + listing.images.length) % listing.images.length)
  return <><section className="property-gallery" aria-label={`Galería de ${listing.title}`} onKeyDown={(event) => { if (event.key === 'ArrowRight') next(); if (event.key === 'ArrowLeft') previous() }} tabIndex={0}><div className="gallery-main"><img src={listing.images[index] || fallbackImage} onError={imageFallback} alt={`Habitación en ${listing.area}, foto ${index + 1} de ${listing.images.length}`} width="1200" height="800" /><button type="button" className="gallery-prev" onClick={previous} aria-label="Foto anterior"><ChevronLeft /></button><button type="button" className="gallery-next" onClick={next} aria-label="Foto siguiente"><ChevronRight /></button><span>{index + 1}/{listing.images.length}</span></div><div className="gallery-thumbs">{listing.images.slice(1, 5).map((image, thumbIndex) => <button key={`${image}-${thumbIndex}`} type="button" onClick={() => thumbIndex === 3 ? setOpen(true) : setIndex(thumbIndex + 1)} aria-label={thumbIndex === 3 ? 'Ver todas las fotos' : `Ver foto ${thumbIndex + 2}`}><img src={image} onError={imageFallback} alt="" width="400" height="280" />{thumbIndex === 3 ? <span><Expand />Ver todas</span> : null}</button>)}</div><Button className="gallery-all-button" variant="outline" onClick={() => setOpen(true)}><Expand data-icon="inline-start" />Ver todas las fotos ({listing.images.length})</Button></section><Dialog open={open} onOpenChange={setOpen}><DialogContent className="gallery-dialog"><DialogHeader><DialogTitle>Todas las fotos</DialogTitle><DialogDescription>{listing.title} · {listing.images.length} imágenes</DialogDescription></DialogHeader><div className="gallery-dialog__grid">{listing.images.map((image, imageIndex) => <button type="button" key={`${image}-${imageIndex}`} onClick={() => { setIndex(imageIndex); setOpen(false) }} aria-label={`Abrir foto ${imageIndex + 1}`}><img src={image} onError={imageFallback} alt={`Habitación en ${listing.area}, foto ${imageIndex + 1}`} width="720" height="480" loading="lazy" /></button>)}</div></DialogContent></Dialog></>
}

export function ContactPanel({ listing, mobile = false }: { listing: Listing; mobile?: boolean }) {
  const [confirmed, setConfirmed] = useState(false)
  const [phone, setPhone] = useState(false)
  const checkboxId = useId()
  const contactText = encodeURIComponent(`Hola, me interesa la habitación de ${listing.area}. ¿Sigue disponible?`)
  return <aside id="contacto" className={cn('contact-panel', mobile && 'contact-panel--mobile')} aria-label="Contactar con el anunciante">{mobile ? null : <><PriceBlock listing={listing} large /><p>{listing.bills} · {listing.deposit}</p><Separator /><div className="owner-row"><Avatar><AvatarFallback>{listing.owner.initials}</AvatarFallback></Avatar><div><strong>{listing.owner.name}</strong><span>{listing.owner.response}</span></div>{listing.owner.verified ? <ShieldCheck aria-label="Identidad verificada" /> : null}</div></>}<label className="condition-confirm" htmlFor={checkboxId}><Checkbox id={checkboxId} checked={confirmed} onCheckedChange={(value) => setConfirmed(value === true)} /><span>Confirmo que he leído y cumplo las condiciones principales.</span></label><div className="contact-actions"><Button asChild={confirmed} disabled={!confirmed}>{confirmed ? <a href={`https://wa.me/${(listing.contactPhone || '34600112233').replace(/\D/g, '')}?text=${contactText}`} target="_blank" rel="noreferrer"><MessageCircle data-icon="inline-start" />WhatsApp</a> : <><MessageCircle data-icon="inline-start" />WhatsApp</>}</Button>{mobile ? null : <Button variant="outline" disabled={!confirmed} onClick={() => setPhone(true)}><Phone data-icon="inline-start" />{phone ? listing.contactPhone || '+34 600 112 233' : 'Mostrar teléfono'}</Button>}</div></aside>
}

export function ReportDialog({ listing }: { listing: Listing }) {
  const { addReport } = useApp()
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const [open, setOpen] = useState(false)
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="ghost" className="report-trigger"><CircleAlert data-icon="inline-start" />Denunciar anuncio</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Denunciar este anuncio</DialogTitle><DialogDescription>Revisaremos «{listing.title}». No compartiremos tu identidad con el anunciante.</DialogDescription></DialogHeader><fieldset className="report-options"><legend>Motivo</legend>{['El anuncio ya no está disponible', 'Datos incorrectos', 'Posible fraude', 'Contenido prohibido', 'Contenido discriminatorio', 'Otro motivo'].map((item) => <label key={item}><input type="radio" name="report" value={item} checked={reason === item} onChange={(event) => setReason(event.target.value)} />{item}</label>)}</fieldset><label className="field-label">Comentario opcional<Textarea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} /></label><DialogFooter><Button disabled={!reason} onClick={() => { addReport(listing.id, reason, comment); setOpen(false); toast.success('Denuncia enviada') }}>Enviar denuncia</Button></DialogFooter></DialogContent></Dialog>
}

export function Pagination({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (page: number) => void }) {
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1)
  return <nav className="pagination" aria-label="Paginación"><Button variant="outline" size="icon" disabled={page === 1} onClick={() => onPage(page - 1)} aria-label="Página anterior"><ChevronLeft /></Button>{pages.map((item) => <Button key={item} variant={page === item ? 'default' : 'outline'} size="icon" onClick={() => onPage(item)} aria-current={page === item ? 'page' : undefined}>{item}</Button>)}<Button variant="outline" size="icon" disabled={page === totalPages} onClick={() => onPage(page + 1)} aria-label="Página siguiente"><ChevronRight /></Button></nav>
}

export function getFilteredListings(mode: RentalMode, filters: Filters) { return filterListings(initialListings, mode, filters) }
export function QuickFilters({ resultCount }: { resultCount: number }) { const { filters, setFilters, activeFilterCount } = useApp(); const chips = [{ label: 'Hasta 500 €', active: filters.maxPrice === 500, apply: () => setFilters({ ...filters, maxPrice: filters.maxPrice === 500 ? defaultFilters.maxPrice : 500 }) }, { label: 'Gastos incluidos', active: filters.billsIncluded, apply: () => setFilters({ ...filters, billsIncluded: !filters.billsIncluded }) }, { label: 'Baño privado', active: filters.bathroom === 'Baño privado', apply: () => setFilters({ ...filters, bathroom: filters.bathroom === 'Baño privado' ? 'Cualquiera' : 'Baño privado' }) }, { label: 'Empadronamiento', active: filters.empadronamiento === 'Sí', apply: () => setFilters({ ...filters, empadronamiento: filters.empadronamiento === 'Sí' ? 'Cualquiera' : 'Sí' }) }]; return <div className="quick-filters" aria-label="Filtros rápidos">{chips.map((chip) => <Button key={chip.label} variant={chip.active ? 'default' : 'outline'} aria-pressed={chip.active} onClick={chip.apply}>{chip.label}</Button>)}<FilterButton resultCount={resultCount} />{activeFilterCount ? <span className="active-filter-note" aria-live="polite">{activeFilterCount} activos</span> : null}</div> }
export function FeatureIcon({ icon: Icon, title, children }: { icon: typeof Home; title: string; children: ReactNode }) { return <div className="feature-icon"><div><Icon aria-hidden="true" /></div><h3>{title}</h3><p>{children}</p></div> }
export const featureIcons = { Home, ShieldCheck, Sparkles, Bath, UsersRound }
