import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bath, BedDouble, CalendarDays, ChevronLeft, ChevronRight, CigaretteOff, CircleAlert, Euro, Expand, ExternalLink, Heart, Home, MapPin, MessageCircle, PawPrint, Phone, Search, ShieldCheck, SlidersHorizontal, Sparkles, UsersRound } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { Slider } from '@/components/ui/slider'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { areas, listings } from '@/data/listings'
import type { Filters, Listing, RentalMode } from '@/types'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'

export function RentalTypeSwitch({ compact = false }: { compact?: boolean }) {
  const { rentalMode, setRentalMode } = useApp()
  return (
    <div className={cn('rental-switch', compact && 'rental-switch--compact')} role="group" aria-label="Tipo de alquiler">
      <button type="button" onClick={() => setRentalMode('long')} aria-pressed={rentalMode === 'long'}>Larga estancia</button>
      <button type="button" onClick={() => setRentalMode('holiday')} aria-pressed={rentalMode === 'holiday'}>Alquiler vacacional</button>
    </div>
  )
}

export function SearchLocationInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="search-location">
      <label htmlFor={id}>Ciudad, barrio o zona</label>
      <div><MapPin aria-hidden="true" /><Input id={id} value={value} onChange={(event) => onChange(event.target.value)} placeholder="Ej. Los Cristianos" /></div>
    </div>
  )
}

export function SearchBar({ compact = false }: { compact?: boolean }) {
  const { query, setQuery } = useApp()
  const navigate = useNavigate()
  const submit = (event: FormEvent) => { event.preventDefault(); navigate(`/buscar?q=${encodeURIComponent(query)}`) }
  return (
    <form className={cn('search-bar', compact && 'search-bar--compact')} onSubmit={submit} role="search">
      <SearchLocationInput value={query} onChange={setQuery} />
      {compact ? null : <div className="search-date"><label htmlFor="move-date">Entrada</label><div><CalendarDays aria-hidden="true" /><Input id="move-date" type="date" defaultValue="2026-08-01" /></div></div>}
      <Button size="lg" type="submit"><Search data-icon="inline-start" />Buscar</Button>
    </form>
  )
}

const restrictionTone = (text: string) => {
  if (text.includes('Gastos') || text.includes('Parejas') || text.includes('Empadronamiento posible')) return 'positive'
  if (text.includes('Solo') || text.includes('Sin') || text.includes('No fumar')) return 'restriction'
  return 'neutral'
}

const restrictionIcon = (text: string) => {
  if (text.includes('mascota')) return PawPrint
  if (text.includes('fumar')) return CigaretteOff
  if (text.includes('mes') || text.includes('junio')) return CalendarDays
  if (text.includes('Gastos')) return Euro
  if (text.includes('Parejas') || text.includes('hombre') || text.includes('mujer') || text.includes('género') || text.includes('personas')) return UsersRound
  return ShieldCheck
}

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
  const { locale } = useI18n()
  return <div className={cn('price-block', large && 'price-block--large')}><strong>{new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(listing.price)}</strong><span>/{listing.cadence}</span></div>
}

export function PropertyCard({ listing, compact = false, selected = false, onFocus }: { listing: Listing; compact?: boolean; selected?: boolean; onFocus?: () => void }) {
  return (
    <article className={cn('property-card', compact && 'property-card--compact', selected && 'is-selected')} onMouseEnter={onFocus} onFocus={onFocus}>
      <div className="property-card__media">
        <Link to={`/habitacion/${listing.id}`} aria-label={`Ver ${listing.title}`}><img src={listing.images[0]} alt={`Habitación en ${listing.area}`} width="720" height="480" loading="eager" /></Link>
        <span className="image-counter">1/{listing.images.length}</span><FavoriteButton listing={listing} />
        {listing.status === 'Publicado' ? <span className="listing-status">Verificado</span> : null}
      </div>
      <div className="property-card__content">
        <div className="card-topline"><PriceBlock listing={listing} /><span>{listing.bills}</span></div>
        <h3><Link to={`/habitacion/${listing.id}`}>{listing.title}</Link></h3>
        <p className="property-location"><MapPin aria-hidden="true" />{listing.area}, {listing.city}</p>
        <div className="property-facts"><span><BedDouble aria-hidden="true" />{listing.roomType}</span><span><CalendarDays aria-hidden="true" />{listing.available}</span></div>
        {compact ? null : <p className="property-description">{listing.description}</p>}
        <div className="badge-row">{listing.restrictions.slice(0, compact ? 2 : 4).map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div>
        {listing.source ? <p className="property-source">{listing.source}</p> : null}
      </div>
    </article>
  )
}

export function LoadingSkeleton({ count = 3 }: { count?: number }) {
  return <div className="skeleton-list" aria-label="Cargando habitaciones" aria-busy="true">{Array.from({ length: count }).map((_, index) => <div className="property-skeleton" key={index}><Skeleton className="h-full min-h-52" /><div><Skeleton className="h-7 w-28" /><Skeleton className="h-5 w-4/5" /><Skeleton className="h-4 w-1/2" /><Skeleton className="h-16 w-full" /></div></div>)}</div>
}

export function EmptyState({ favorites = false }: { favorites?: boolean }) {
  return <Empty className="empty-state"><EmptyHeader><EmptyMedia variant="icon">{favorites ? <Heart /> : <Search />}</EmptyMedia><EmptyTitle>{favorites ? 'Aún no has guardado habitaciones' : 'No hay habitaciones con estos filtros'}</EmptyTitle><EmptyDescription>{favorites ? 'Guarda las que te gusten para compararlas aquí.' : 'Prueba a ampliar el precio o quitar alguna condición.'}</EmptyDescription></EmptyHeader><EmptyContent><Button asChild><Link to="/buscar">{favorites ? 'Explorar habitaciones' : 'Limpiar y buscar'}</Link></Button></EmptyContent></Empty>
}

export function ErrorState() {
  return <Alert variant="destructive"><CircleAlert /><AlertTitle>No hemos podido cargar los resultados</AlertTitle><AlertDescription>Comprueba tu conexión y vuelve a intentarlo. Tus filtros siguen guardados. <Button variant="outline" size="sm" onClick={() => location.reload()}>Reintentar</Button></AlertDescription></Alert>
}

const filterConditions = ['Solo hombre', 'Solo mujer', 'Parejas permitidas', 'Sin preferencia de género', 'Niños permitidos', 'Mascotas permitidas', 'Empadronamiento posible', 'No fumar']

function CheckOption({ label, checked, onCheckedChange }: { label: string; checked: boolean; onCheckedChange: (checked: boolean) => void }) {
  const id = `filter-${label.toLowerCase().replaceAll(' ', '-')}`
  return <label className="check-option" htmlFor={id}><Checkbox id={id} checked={checked} onCheckedChange={(value) => onCheckedChange(value === true)} /><span>{label}</span></label>
}

function FilterPanel({ value, onChange }: { value: Filters; onChange: (value: Filters) => void }) {
  const update = <K extends keyof Filters>(key: K, next: Filters[K]) => onChange({ ...value, [key]: next })
  return (
    <div className="filter-panel">
      <section className="filter-section"><h3>Precio mensual</h3><div className="range-values"><span>{value.minPrice} €</span><span>{value.maxPrice >= 1000 ? '1.000 €+' : `${value.maxPrice} €`}</span></div><Slider min={0} max={1000} step={25} value={[value.minPrice, value.maxPrice]} onValueChange={([min, max]) => onChange({ ...value, minPrice: min, maxPrice: max })} aria-label="Rango de precio" /></section>
      <Separator />
      <fieldset className="filter-section"><legend>Zona</legend><div className="checks-grid">{areas.map((area) => <CheckOption key={area} label={area} checked={value.areas.includes(area)} onCheckedChange={(checked) => update('areas', checked ? [...value.areas, area] : value.areas.filter((item) => item !== area))} />)}</div></fieldset>
      <Separator />
      <fieldset className="filter-section"><legend>Tipo de habitación</legend><div className="radio-cards">{['Cualquiera', 'Habitación individual', 'Habitación compartida', 'Estudio'].map((option) => <label key={option}><input type="radio" name="room-type" checked={value.roomType === option} onChange={() => update('roomType', option)} /><span>{option}</span></label>)}</div></fieldset>
      <Separator />
      <section className="filter-section"><h3>Disponibilidad y estancia</h3><label className="field-label">Disponible desde<Input type="date" value={value.available} onChange={(event) => update('available', event.target.value)} /></label><label className="field-label">Estancia mínima<select value={value.minStay} onChange={(event) => update('minStay', event.target.value)}><option>Cualquiera</option><option>1 mes</option><option>3 meses</option><option>6 meses</option><option>Curso académico</option></select></label></section>
      <Separator />
      <fieldset className="filter-section"><legend>Convivencia y condiciones</legend><div className="checks-grid">{filterConditions.map((condition) => <CheckOption key={condition} label={condition} checked={value.conditions.includes(condition)} onCheckedChange={(checked) => update('conditions', checked ? [...value.conditions, condition] : value.conditions.filter((item) => item !== condition))} />)}</div></fieldset>
      <Separator />
      <section className="filter-section"><h3>Espacios y equipamiento</h3><label className="field-label">Baño<select value={value.bathroom} onChange={(event) => update('bathroom', event.target.value)}><option>Cualquiera</option><option>Baño privado</option><option>Baño compartido</option></select></label><label className="field-label">Cocina<select value={value.kitchen} onChange={(event) => update('kitchen', event.target.value)}><option>Cualquiera</option><option>Cocina privada</option><option>Cocina compartida</option></select></label><CheckOption label="Amueblada" checked={value.furnished} onCheckedChange={(checked) => update('furnished', checked)} /><CheckOption label="Gastos incluidos" checked={value.billsIncluded} onCheckedChange={(checked) => update('billsIncluded', checked)} /></section>
      <Separator />
      <section className="filter-section"><h3>Fianza y vivienda</h3><label className="field-label">Depósito<select value={value.deposit} onChange={(event) => update('deposit', event.target.value)}><option>Cualquiera</option><option>Sin fianza</option><option>Hasta 1 mes</option><option>Más de 1 mes</option></select></label><label className="field-label">Personas en la vivienda<select value={value.occupants} onChange={(event) => update('occupants', event.target.value)}><option>Cualquiera</option><option>1–2</option><option>3–4</option><option>5 o más</option></select></label></section>
    </div>
  )
}

export function FilterButton({ resultCount }: { resultCount: number }) {
  const { filters, setFilters, resetFilters, activeFilterCount } = useApp()
  const [draft, setDraft] = useState(filters)
  const [open, setOpen] = useState(false)
  useEffect(() => { if (open) setDraft(filters) }, [open, filters])
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild><Button variant="outline"><SlidersHorizontal data-icon="inline-start" />Todos los filtros{activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}</Button></SheetTrigger>
      <SheetContent className="filter-drawer">
        <SheetHeader><SheetTitle>Filtros</SheetTitle><SheetDescription>Ajusta las condiciones que realmente importan para convivir.</SheetDescription></SheetHeader>
        <FilterPanel value={draft} onChange={setDraft} />
        <SheetFooter className="filter-footer"><Button variant="ghost" onClick={() => { setDraft({ ...filters, ...{ minPrice: 0, maxPrice: 1000, areas: [], roomType: 'Cualquiera', available: '', minStay: 'Cualquiera', conditions: [], bathroom: 'Cualquiera', kitchen: 'Cualquiera', furnished: false, billsIncluded: false, deposit: 'Cualquiera', occupants: 'Cualquiera' } }); resetFilters() }}>Limpiar filtros</Button><Button onClick={() => { setFilters(draft); setOpen(false); toast.success(`${resultCount} habitaciones encontradas`) }}>Mostrar {resultCount} habitaciones</Button></SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

type MapCenter = Pick<Listing['coordinates'], 'lat' | 'lng'>

export interface MapAdapter {
  getEmbedUrl(center: MapCenter, zoom: number, language: string, marker?: MapCenter): string
  getExternalUrl(center: MapCenter, zoom: number, marker?: MapCenter): string
}

export const googleSatelliteMapAdapter: MapAdapter = {
  getEmbedUrl: ({ lat, lng }, zoom, language, marker) => {
    const location = marker ? `q=${marker.lat},${marker.lng}` : `ll=${lat},${lng}`
    return `https://www.google.com/maps?${location}&t=k&z=${zoom}&output=embed&hl=${language}`
  },
  getExternalUrl: ({ lat, lng }, zoom, marker) => marker
    ? `https://www.google.com/maps?q=${marker.lat},${marker.lng}&t=k&z=${zoom}`
    : `https://www.google.com/maps/@?api=1&map_action=map&center=${lat}%2C${lng}&zoom=${zoom}&basemap=satellite`,
}

const tenerifeCenter: MapCenter = { lat: 28.2915637, lng: -16.6291304 }

export function MapView({ items, selectedId, onSelect, fullScreen = false, showPreview = true }: { items: Listing[]; selectedId?: string; onSelect: (id: string) => void; fullScreen?: boolean; showPreview?: boolean }) {
  const { language, locale } = useI18n()
  const selected = items.find((item) => item.id === selectedId)
  const center = selected?.coordinates ?? tenerifeCenter
  const marker = selected?.coordinates
  const zoom = selected ? 14 : 10
  const price = (item: Listing) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(item.price)
  return (
    <section className={cn('mock-map', fullScreen && 'mock-map--fullscreen')} aria-label="Mapa de habitaciones">
      <div className="google-map-frame-wrap">
        <iframe key={`${center.lat}-${center.lng}-${language}-${selectedId ?? 'island'}`} className="google-map-frame" src={googleSatelliteMapAdapter.getEmbedUrl(center, zoom, language, marker)} title="Mapa satelital interactivo de Tenerife" loading={fullScreen ? 'eager' : 'lazy'} allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />
      </div>
      <div className="map-location-dock">
        <div className="map-location-list" role="group" aria-label="Ubicaciones disponibles">
          {items.map((item) => <button key={item.id} type="button" className={cn('map-location-button', item.id === selectedId && 'is-active')} onClick={() => onSelect(item.id)} aria-label={`Centrar mapa en ${item.area}, ${item.price} euros`} aria-pressed={item.id === selectedId}><MapPin aria-hidden="true" /><span><strong>{item.area}</strong><small>{price(item)}/{item.cadence}</small></span></button>)}
        </div>
        <div className="map-location-meta">
          <p><ShieldCheck aria-hidden="true" />El marcador corresponde a las coordenadas del anuncio.</p>
          <div className="map-location-actions">
            <Button asChild variant="outline" size="sm"><a href={googleSatelliteMapAdapter.getExternalUrl(center, zoom, marker)} target="_blank" rel="noreferrer">Abrir en Google Maps<ExternalLink data-icon="inline-end" /></a></Button>
            {selected && showPreview ? <Button asChild size="sm"><Link to={`/habitacion/${selected.id}`}>Ver anuncio</Link></Button> : null}
          </div>
        </div>
      </div>
    </section>
  )
}

export function PropertyGallery({ listing }: { listing: Listing }) {
  const [index, setIndex] = useState(0)
  const next = () => setIndex((value) => (value + 1) % listing.images.length)
  const previous = () => setIndex((value) => (value - 1 + listing.images.length) % listing.images.length)
  return (
    <section className="property-gallery" aria-label={`Galería de ${listing.title}`} onKeyDown={(event) => { if (event.key === 'ArrowRight') next(); if (event.key === 'ArrowLeft') previous() }} tabIndex={0}>
      <div className="gallery-main"><img src={listing.images[index]} alt={`Habitación en ${listing.area}, foto ${index + 1} de ${listing.images.length}`} width="1200" height="800" /><button type="button" className="gallery-prev" onClick={previous} aria-label="Foto anterior"><ChevronLeft /></button><button type="button" className="gallery-next" onClick={next} aria-label="Foto siguiente"><ChevronRight /></button><span>{index + 1}/{listing.images.length}</span></div>
      <div className="gallery-thumbs">{listing.images.slice(1, 5).map((image, thumbIndex) => <button key={image} type="button" onClick={() => setIndex(thumbIndex + 1)} aria-label={`Ver foto ${thumbIndex + 2}`}><img src={image} alt="" width="400" height="280" />{thumbIndex === 3 ? <span><Expand />Ver todas</span> : null}</button>)}</div>
    </section>
  )
}

export function ContactPanel({ listing, mobile = false }: { listing: Listing; mobile?: boolean }) {
  const [confirmed, setConfirmed] = useState(false)
  const [phone, setPhone] = useState(false)
  const [messageOpen, setMessageOpen] = useState(false)
  const checkboxId = useId()
  return (
    <aside className={cn('contact-panel', mobile && 'contact-panel--mobile')} aria-label="Contactar con el anunciante">
      {mobile ? null : <><PriceBlock listing={listing} large /><p>{listing.bills} · {listing.deposit}</p><Separator /><div className="owner-row"><Avatar><AvatarFallback>{listing.owner.initials}</AvatarFallback></Avatar><div><strong>{listing.owner.name}</strong><span>{listing.owner.response}</span></div>{listing.owner.verified ? <ShieldCheck aria-label="Identidad verificada" /> : null}</div></>}
      <label className="condition-confirm" htmlFor={checkboxId}><Checkbox id={checkboxId} checked={confirmed} onCheckedChange={(value) => setConfirmed(value === true)} /><span>Confirmo que cumplo las condiciones principales del anuncio.</span></label>
      <div className="contact-actions">
        <Button disabled={!confirmed} onClick={() => toast.success('Abriendo conversación de WhatsApp')}><MessageCircle data-icon="inline-start" />WhatsApp</Button>
        {mobile ? null : <Button variant="outline" disabled={!confirmed} onClick={() => setPhone(true)}><Phone data-icon="inline-start" />{phone ? '+34 600 112 233' : 'Mostrar teléfono'}</Button>}
        <Dialog open={messageOpen} onOpenChange={setMessageOpen}>
          <DialogTrigger asChild><Button variant="outline" disabled={!confirmed}><MessageCircle data-icon="inline-start" />Mensaje</Button></DialogTrigger>
          <DialogContent><DialogHeader><DialogTitle>Escribir a {listing.owner.name}</DialogTitle><DialogDescription>Cuéntale brevemente quién eres y cuándo quieres entrar.</DialogDescription></DialogHeader><label className="field-label">Tu mensaje<Textarea defaultValue={`Hola, me interesa la habitación de ${listing.area}. ¿Sigue disponible?`} rows={5} /></label><DialogFooter><Button onClick={() => { setMessageOpen(false); toast.success('Mensaje enviado. Te avisaremos cuando respondan.') }}>Enviar mensaje</Button></DialogFooter></DialogContent>
        </Dialog>
      </div>
    </aside>
  )
}

export function ReportDialog({ listing }: { listing: Listing }) {
  const [reason, setReason] = useState('')
  return (
    <Dialog><DialogTrigger asChild><Button variant="ghost" className="report-trigger"><CircleAlert data-icon="inline-start" />Denunciar anuncio</Button></DialogTrigger><DialogContent><DialogHeader><DialogTitle>Denunciar este anuncio</DialogTitle><DialogDescription>Revisaremos el anuncio «{listing.title}». No compartiremos tu identidad con el anunciante.</DialogDescription></DialogHeader><fieldset className="report-options"><legend>Motivo</legend>{['El anuncio ya no está disponible', 'Datos incorrectos', 'Posible fraude', 'Contenido prohibido', 'Contenido discriminatorio', 'Otro motivo'].map((item) => <label key={item}><input type="radio" name="report" value={item} checked={reason === item} onChange={(event) => setReason(event.target.value)} />{item}</label>)}</fieldset><label className="field-label">Comentario opcional<Textarea rows={3} /></label><DialogFooter><Button disabled={!reason} onClick={() => toast.success('Denuncia enviada. Gracias por ayudarnos a cuidar la comunidad.')}>Enviar denuncia</Button></DialogFooter></DialogContent></Dialog>
  )
}

export function Pagination({ page, onPage }: { page: number; onPage: (page: number) => void }) {
  return <nav className="pagination" aria-label="Paginación"><Button variant="outline" size="icon" disabled={page === 1} onClick={() => onPage(page - 1)} aria-label="Página anterior"><ChevronLeft /></Button>{[1, 2, 3].map((item) => <Button key={item} variant={page === item ? 'default' : 'outline'} size="icon" onClick={() => onPage(item)} aria-current={page === item ? 'page' : undefined}>{item}</Button>)}<Button variant="outline" size="icon" onClick={() => onPage(page + 1)} aria-label="Página siguiente"><ChevronRight /></Button></nav>
}

export function getFilteredListings(mode: RentalMode, filters: Filters) {
  return listings.filter((listing) => {
    if (listing.rentalMode !== mode) return false
    if (listing.price < filters.minPrice || listing.price > filters.maxPrice) return false
    if (filters.areas.length && !filters.areas.includes(listing.area)) return false
    if (filters.roomType !== 'Cualquiera' && listing.roomType !== filters.roomType) return false
    if (filters.conditions.length && !filters.conditions.every((condition) => listing.restrictions.includes(condition))) return false
    if (filters.bathroom !== 'Cualquiera' && listing.bathroom !== filters.bathroom) return false
    if (filters.kitchen !== 'Cualquiera' && listing.kitchen !== filters.kitchen) return false
    if (filters.furnished && !listing.furnished) return false
    if (filters.billsIncluded && !listing.bills.includes('incluid')) return false
    return true
  })
}

export function QuickFilters({ resultCount }: { resultCount: number }) {
  const { filters, setFilters, activeFilterCount } = useApp()
  const chips = useMemo(() => [
    { label: 'Hasta 500 €', active: filters.maxPrice === 500, apply: () => setFilters({ ...filters, maxPrice: filters.maxPrice === 500 ? 1000 : 500 }) },
    { label: 'Gastos incluidos', active: filters.billsIncluded, apply: () => setFilters({ ...filters, billsIncluded: !filters.billsIncluded }) },
    { label: 'Baño privado', active: filters.bathroom === 'Baño privado', apply: () => setFilters({ ...filters, bathroom: filters.bathroom === 'Baño privado' ? 'Cualquiera' : 'Baño privado' }) },
    { label: 'Empadronamiento', active: filters.conditions.includes('Empadronamiento posible'), apply: () => setFilters({ ...filters, conditions: filters.conditions.includes('Empadronamiento posible') ? filters.conditions.filter((item) => item !== 'Empadronamiento posible') : [...filters.conditions, 'Empadronamiento posible'] }) },
  ], [filters, setFilters])
  return <div className="quick-filters" aria-label="Filtros rápidos">{chips.map((chip) => <Button key={chip.label} variant={chip.active ? 'default' : 'outline'} aria-pressed={chip.active} onClick={chip.apply}>{chip.label}</Button>)}<FilterButton resultCount={resultCount} />{activeFilterCount ? <span className="active-filter-note" aria-live="polite">{activeFilterCount} activos</span> : null}</div>
}

export function FeatureIcon({ icon: Icon, title, children }: { icon: typeof Home; title: string; children: ReactNode }) {
  return <div className="feature-icon"><div><Icon aria-hidden="true" /></div><h3>{title}</h3><p>{children}</p></div>
}

export const featureIcons = { Home, ShieldCheck, Sparkles, Bath, UsersRound }
