import { ArrowLeft, Bath, BedDouble, CalendarDays, Check, CookingPot, Heart, Home, MapPin, Ruler, Share2, ShieldCheck, Trash2, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Separator } from '@/components/ui/separator'
import { ContactPanel, MapView, PriceBlock, PropertyBadge, PropertyCard, PropertyGallery, ReportDialog } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { listings } from '@/data/listings'

export function ListingPage() {
  const { id } = useParams()
  const { favorites, toggleFavorite } = useApp()
  const listing = listings.find((item) => item.id === id)
  const primaryRestriction = listing?.restrictions.find((item) => item.startsWith('Solo '))
  const [restrictionOpen, setRestrictionOpen] = useState(Boolean(primaryRestriction))
  if (!listing) return <Navigate to="/buscar" replace />
  const similar = listings.filter((item) => item.id !== listing.id && item.rentalMode === listing.rentalMode).slice(0, 3)
  const saved = favorites.has(listing.id)
  const restrictionTitle = primaryRestriction === 'Solo hombre' ? 'Esta habitación es solo para un hombre' : primaryRestriction === 'Solo mujer' ? 'Esta habitación es solo para una mujer' : primaryRestriction
  return (
    <article className="listing-page idealista-listing-page">
      {primaryRestriction ? <AlertDialog open={restrictionOpen} onOpenChange={setRestrictionOpen}><AlertDialogContent className="restriction-dialog"><AlertDialogHeader><span className="restriction-dialog__eyebrow"><UsersRound aria-hidden="true" />Condición principal del anuncio</span><AlertDialogTitle>{restrictionTitle}</AlertDialogTitle><AlertDialogDescription>El anunciante solo atenderá solicitudes que cumplan esta condición. Compruébala antes de continuar.</AlertDialogDescription></AlertDialogHeader><div className="restriction-dialog__badges">{listing.restrictions.slice(0, 4).map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div><AlertDialogFooter><AlertDialogCancel asChild><Link to="/buscar">Volver al listado</Link></AlertDialogCancel><AlertDialogAction onClick={() => setRestrictionOpen(false)}>Entendido, cumplo la condición</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog> : null}
      <div className="container listing-actionbar"><Button asChild variant="ghost" size="sm"><Link to="/buscar"><ArrowLeft data-icon="inline-start" />Volver al listado</Link></Button><div><Button variant="ghost" size="sm" onClick={() => toast.success('Enlace copiado')}><Share2 data-icon="inline-start" />Compartir</Button><Button variant="ghost" size="sm" onClick={() => toast.success('Anuncio descartado')}><Trash2 data-icon="inline-start" />Descartar</Button><Button variant="ghost" size="sm" onClick={() => toggleFavorite(listing.id)} aria-pressed={saved}><Heart data-icon="inline-start" fill={saved ? 'currentColor' : 'none'} />{saved ? 'Guardado' : 'Guardar'}</Button></div></div>
      <div className="container"><PropertyGallery listing={listing} /></div>
      <div className="container listing-layout">
        <div className="listing-main">
          <header className="listing-title"><div><h1>Habitación en {listing.area}, {listing.city}</h1><p>{listing.title}</p><span className="listing-address"><MapPin aria-hidden="true" />{listing.approximateAddress}</span></div><PriceBlock listing={listing} large /></header>
          <div className="listing-keyfacts"><span>{listing.occupants} hab.</span><span>{listing.occupants} personas</span><span>{listing.bathroom}</span><span>{listing.restrictions.includes('No fumar') ? 'No se puede fumar' : 'Consulta condiciones'}</span></div>
          {primaryRestriction ? <section className="listing-restriction-notice" aria-labelledby="restriction-title"><UsersRound aria-hidden="true" /><div><span>Importante antes de contactar</span><h2 id="restriction-title">{restrictionTitle}</h2><p>El anunciante ha indicado esta condición para la habitación.</p></div></section> : null}
          <Separator />
          <section className="listing-section"><h2>Descripción</h2><p className="prose">{listing.description}</p><p className="prose">{listing.homeDescription}</p></section>
          <Separator />
          <section className="listing-section"><h2>Características básicas</h2><ul className="idealista-feature-list"><li><Home />Vivienda compartida con {listing.occupants} residentes</li><li><BedDouble />{listing.roomType}</li><li><Bath />{listing.bathroom}</li><li><CookingPot />{listing.kitchen}</li><li><Ruler />Habitación {listing.furnished ? 'amueblada' : 'sin amueblar'}</li><li><CalendarDays />{listing.available}</li></ul></section>
          <Separator />
          <section className="listing-section"><h2>Características de la habitación</h2><div className="amenities-grid">{listing.amenities.map((amenity) => <span key={amenity}><Check />{amenity}</span>)}</div></section>
          <Separator />
          <section className="listing-section conditions-block"><h2>Normas y convivencia</h2><p>Comprueba estas condiciones antes de escribir al anunciante.</p><div className="badge-row badge-row--large">{listing.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></section>
          <Separator />
          <section className="listing-section"><h2>Precio y disponibilidad</h2><dl className="detail-list"><div><dt>Renta</dt><dd>{listing.price} €/{listing.cadence}</dd></div><div><dt>Gastos</dt><dd>{listing.bills}</dd></div><div><dt>Fianza</dt><dd>{listing.deposit}</dd></div><div><dt>Entrada</dt><dd>{listing.available}</dd></div><div><dt>Estancia mínima</dt><dd>{listing.minimumStay}</dd></div></dl></section>
          <Separator />
          <section className="listing-section"><h2>Ubicación</h2><p className="map-intro">El marcador corresponde a las coordenadas guardadas en el anuncio.</p><div className="detail-map"><MapView items={[listing]} selectedId={listing.id} onSelect={() => undefined} showPreview={false} /></div></section>
          <Separator />
          <section className="listing-section owner-detail"><div className="owner-monogram">{listing.owner.initials}</div><div><span>Anunciante</span><h2>{listing.owner.name}</h2><p>{listing.owner.since} · {listing.owner.response}</p><p>{listing.owner.verified ? 'Identidad y teléfono verificados por 112233.es.' : 'Identidad pendiente de verificación.'}</p></div>{listing.owner.verified ? <Badge variant="outline"><ShieldCheck />Anunciante verificado</Badge> : null}</section>
          <div className="listing-meta"><span>{listing.publishedAt}</span><span>Referencia {listing.id.slice(-5).toUpperCase()}</span><ReportDialog listing={listing} /></div>
        </div>
        <div className="listing-aside"><ContactPanel listing={listing} /></div>
      </div>
      <section className="section section--surface"><div className="container"><div className="section-heading idealista-section-heading"><div><h2>También te puede interesar</h2><p>Habitaciones similares en Tenerife.</p></div><Button asChild variant="outline"><Link to="/buscar">Ver más</Link></Button></div><div className="property-grid">{similar.map((item) => <PropertyCard key={item.id} listing={item} compact />)}</div></div></section>
      <div className="mobile-contact-bar"><ContactPanel listing={listing} mobile /></div>
    </article>
  )
}
