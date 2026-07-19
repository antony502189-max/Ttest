import { ArrowLeft, Bath, BedDouble, CalendarDays, Check, CookingPot, Home, MapPin, Ruler, ShieldCheck, UsersRound } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ContactPanel, MapView, PriceBlock, PropertyBadge, PropertyCard, PropertyGallery, ReportDialog } from '@/components/marketplace'
import { listings } from '@/data/listings'

export function ListingPage() {
  const { id } = useParams()
  const listing = listings.find((item) => item.id === id)
  if (!listing) return <Navigate to="/buscar" replace />
  const similar = listings.filter((item) => item.id !== listing.id && item.rentalMode === listing.rentalMode).slice(0, 3)
  return (
    <article className="listing-page">
      <div className="container listing-breadcrumb"><Button asChild variant="ghost" size="sm"><Link to="/buscar"><ArrowLeft data-icon="inline-start" />Volver a resultados</Link></Button><span>Habitaciones / {listing.area}</span></div>
      <div className="container"><PropertyGallery listing={listing} /></div>
      <div className="container listing-layout">
        <div className="listing-main">
          <header className="listing-title"><div><div className="badge-row"><Badge>Disponible</Badge>{listing.owner.verified ? <Badge variant="outline"><ShieldCheck />Anunciante verificado</Badge> : null}</div><h1>{listing.title}</h1><p><MapPin />{listing.area}, {listing.city} · {listing.approximateAddress}</p></div><PriceBlock listing={listing} large /></header>
          <div className="listing-keyfacts"><div><BedDouble /><span>{listing.roomType}</span></div><div><CalendarDays /><span>{listing.available}</span></div><div><Bath /><span>{listing.bathroom}</span></div><div><UsersRound /><span>{listing.occupants} personas en casa</span></div></div>
          <Separator />
          <section className="listing-section"><h2>Sobre la habitación</h2><p className="prose">{listing.description}</p><div className="amenities-grid">{listing.amenities.map((amenity) => <span key={amenity}><Check />{amenity}</span>)}</div></section>
          <Separator />
          <section className="listing-section"><h2>La vivienda</h2><p className="prose">{listing.homeDescription}</p><div className="spec-grid"><div><Home /><strong>Vivienda compartida</strong><span>{listing.occupants} residentes</span></div><div><CookingPot /><strong>{listing.kitchen}</strong><span>Equipada</span></div><div><Bath /><strong>{listing.bathroom}</strong><span>Uso indicado</span></div><div><Ruler /><strong>Habitación amueblada</strong><span>{listing.furnished ? 'Sí' : 'No'}</span></div></div></section>
          <Separator />
          <section className="listing-section conditions-block"><span className="eyebrow">Antes de contactar</span><h2>Condiciones de convivencia</h2><p>Comprueba que encajas con las condiciones indicadas por el anunciante.</p><div className="badge-row badge-row--large">{listing.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></section>
          <section className="listing-section"><h2>Precio y disponibilidad</h2><dl className="detail-list"><div><dt>Renta</dt><dd>{listing.price} €/{listing.cadence}</dd></div><div><dt>Gastos</dt><dd>{listing.bills}</dd></div><div><dt>Fianza</dt><dd>{listing.deposit}</dd></div><div><dt>Entrada</dt><dd>{listing.available}</dd></div><div><dt>Estancia</dt><dd>{listing.minimumStay}</dd></div></dl></section>
          <Separator />
          <section className="listing-section"><h2>Ubicación aproximada</h2><p className="map-intro">El punto se desplaza ligeramente para no revelar la dirección exacta.</p><div className="detail-map"><MapView items={[listing]} selectedId={listing.id} onSelect={() => undefined} showPreview={false} /></div></section>
          <Separator />
          <section className="listing-section owner-detail"><div className="owner-monogram">{listing.owner.initials}</div><div><span className="eyebrow">Anunciante</span><h2>{listing.owner.name}</h2><p>{listing.owner.since} · {listing.owner.response}</p><p>{listing.owner.verified ? 'Identidad y teléfono verificados por 112233.es.' : 'Identidad pendiente de verificación.'}</p></div></section>
          <div className="listing-meta"><span>{listing.publishedAt}</span><span>Referencia {listing.id.slice(-5).toUpperCase()}</span><ReportDialog listing={listing} /></div>
        </div>
        <div className="listing-aside"><ContactPanel listing={listing} /></div>
      </div>
      <section className="section section--surface"><div className="container"><div className="section-heading"><div><span className="eyebrow">También pueden encajarte</span><h2>Habitaciones similares</h2></div><Button asChild variant="outline"><Link to="/buscar">Ver más</Link></Button></div><div className="property-grid">{similar.map((item) => <PropertyCard key={item.id} listing={item} compact />)}</div></div></section>
      <div className="mobile-contact-bar"><ContactPanel listing={listing} mobile /></div>
    </article>
  )
}
