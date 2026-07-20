import { ArrowLeft, Bath, BedDouble, CalendarDays, Check, CookingPot, Heart, Home, MapPin, Ruler, Share2, ShieldCheck, Trash2, UsersRound } from 'lucide-react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ContactPanel, MapView, PriceBlock, PropertyBadge, PropertyCard, PropertyGallery, ReportDialog } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { formatPublishedAt } from '@/lib/search'

const preferenceTitle = (value?: string) => value === 'Solo hombre' ? 'Este anuncio busca a un hombre' : value === 'Solo mujer' ? 'Este anuncio busca a una mujer' : value

export function ListingPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { allListings, favorites, toggleFavorite, discardListing } = useApp()
  const listing = allListings.find((item) => item.id === id && item.status === 'Publicado')
  if (!listing) return <Navigate to="/buscar" replace />
  const primaryRestriction = listing.restrictions.find((item) => item.startsWith('Solo '))
  const similar = allListings
    .filter((item) => item.id !== listing.id && item.status === 'Publicado' && item.rentalMode === listing.rentalMode)
    .sort((a, b) => Number(b.area === listing.area) - Number(a.area === listing.area) || Math.abs(a.price - listing.price) - Math.abs(b.price - listing.price))
    .slice(0, 3)
  const saved = favorites.has(listing.id)
  const share = async () => {
    const data = { title: listing.title, text: `Habitación en ${listing.area} por ${listing.price} €`, url: window.location.href }
    try {
      if (navigator.share) await navigator.share(data)
      else { await navigator.clipboard.writeText(window.location.href); toast.success('Enlace copiado') }
    } catch (error) { if ((error as DOMException).name !== 'AbortError') toast.error('No se pudo compartir el anuncio') }
  }
  return (
    <article className="listing-page idealista-listing-page">
      <div className="container listing-actionbar"><Button asChild variant="ghost" size="sm"><Link to="/buscar"><ArrowLeft data-icon="inline-start" />Volver al listado</Link></Button><div><Button variant="ghost" size="sm" onClick={share}><Share2 data-icon="inline-start" />Compartir</Button><Button variant="ghost" size="sm" onClick={() => { discardListing(listing.id); toast.success('Anuncio descartado'); navigate('/buscar') }}><Trash2 data-icon="inline-start" />Descartar</Button><Button variant="ghost" size="sm" onClick={() => toggleFavorite(listing.id)} aria-pressed={saved}><Heart data-icon="inline-start" fill={saved ? 'currentColor' : 'none'} />{saved ? 'Guardado' : 'Guardar'}</Button></div></div>
      <div className="container"><PropertyGallery listing={listing} /></div>
      <div className="container listing-layout">
        <div className="listing-main">
          <header className="listing-title"><div><h1>Habitación en {listing.area}, {listing.city}</h1><p>{listing.title}</p><span className="listing-address"><MapPin aria-hidden="true" />{listing.approximateAddress}</span></div><PriceBlock listing={listing} large /></header>
          <div className="listing-keyfacts"><span>{listing.roomType}</span><span>{listing.occupants} personas</span><span>{listing.bathroom}</span><span>{listing.furnished ? 'Amueblada' : 'Sin amueblar'}</span></div>
          {primaryRestriction ? <section className="listing-restriction-notice" aria-labelledby="restriction-title"><UsersRound aria-hidden="true" /><div><span>Condición principal</span><h2 id="restriction-title">{preferenceTitle(primaryRestriction)}</h2><p>Comprueba esta preferencia visible del anunciante antes de contactar. Puedes seguir consultando el anuncio sin interrupciones.</p></div></section> : null}
          <Separator />
          <section className="listing-section"><h2>Descripción</h2><p className="prose">{listing.description}</p><p className="prose">{listing.homeDescription}</p></section>
          <Separator />
          <section className="listing-section"><h2>Características básicas</h2><ul className="idealista-feature-list"><li><Home />Vivienda compartida con {listing.occupants} residentes</li><li><BedDouble />{listing.roomType}</li><li><Bath />{listing.bathroom}</li><li><CookingPot />{listing.kitchen}</li><li><Ruler />Habitación {listing.furnished ? 'amueblada' : 'sin amueblar'}</li><li><CalendarDays />{listing.available}</li></ul></section>
          <Separator />
          <section className="listing-section"><h2>Equipamiento</h2><div className="amenities-grid">{listing.amenities.map((amenity) => <span key={amenity}><Check />{amenity}</span>)}</div></section>
          <Separator />
          <section className="listing-section conditions-block"><h2>Normas y convivencia</h2><p>Todas las condiciones están visibles antes del contacto.</p><div className="badge-row badge-row--large">{listing.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></section>
          <Separator />
          <section className="listing-section"><h2>Precio y disponibilidad</h2><dl className="detail-list"><div><dt>Renta</dt><dd>{listing.price} €/{listing.cadence}</dd></div><div><dt>Gastos</dt><dd>{listing.bills}</dd></div><div><dt>Fianza</dt><dd>{listing.deposit}</dd></div><div><dt>Entrada</dt><dd>{listing.available}</dd></div><div><dt>Estancia mínima</dt><dd>{listing.minimumStay}</dd></div></dl></section>
          <Separator />
          <section className="listing-section"><h2>Ubicación aproximada</h2><p className="map-intro">El marcador protege la dirección exacta.</p><div className="detail-map"><MapView items={[listing]} selectedId={listing.id} onSelect={() => undefined} showPreview={false} /></div></section>
          <Separator />
          <section className="listing-section owner-detail"><div className="owner-monogram">{listing.owner.initials}</div><div><span>Anunciante</span><h2>{listing.owner.name}</h2><p>{listing.owner.since} · {listing.owner.response}</p><p>{listing.owner.verified ? 'Identidad y teléfono verificados por 112233.es.' : 'Identidad pendiente de verificación.'}</p></div>{listing.owner.verified ? <Badge variant="outline"><ShieldCheck />Anunciante verificado</Badge> : null}</section>
          <div className="listing-meta"><span>{formatPublishedAt(listing.publishedAt)}</span><span>Referencia {listing.id.slice(-5).toUpperCase()}</span><span>{listing.source ?? 'Anuncio directo'}</span><ReportDialog listing={listing} /></div>
        </div>
        <div className="listing-aside"><ContactPanel listing={listing} /></div>
      </div>
      <section className="section section--surface"><div className="container"><div className="section-heading idealista-section-heading"><div><h2>También te puede interesar</h2><p>Primero mostramos zona y precio parecidos.</p></div><Button asChild variant="outline"><Link to="/buscar">Ver más</Link></Button></div><div className="property-grid">{similar.map((item) => <PropertyCard key={item.id} listing={item} compact />)}</div></div></section>
      <div className="mobile-contact-bar"><ContactPanel listing={listing} mobile /></div>
    </article>
  )
}
