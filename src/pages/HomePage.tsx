import { ArrowRight, Bell, Map, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { areas } from '@/data/listings'
import { PropertyCard, RentalTypeSwitch, SearchBar } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'

export function HomePage() {
  const { allListings } = useApp()
  const featured = allListings.filter((listing) => listing.status === 'Publicado').slice(0, 3)
  return (
    <div className="home-page idealista-home">
      <section className="idealista-home-hero" aria-labelledby="home-title">
        <img className="idealista-home-hero__image" src={featured[1]?.images[1] ?? featured[0]?.images[0]} alt="Habitación luminosa preparada para alquilar" width="1600" height="900" />
        <div className="idealista-home-hero__shade" />
        <div className="container idealista-home-hero__content">
          <h1 id="home-title">Tu próxima habitación está más cerca de lo que imaginas</h1>
          <div className="idealista-search-box">
            <RentalTypeSwitch />
            <div className="idealista-search-box__type" aria-label="Tipo de inmueble"><span>Tipo de inmueble</span><strong>Habitación</strong></div>
            <SearchBar />
            <Button asChild variant="ghost" className="draw-zone-link"><Link to="/buscar?vista=mapa"><Map data-icon="inline-start" />Seleccionar zona en el mapa</Link></Button>
          </div>
        </div>
      </section>

      <section className="container home-primary-actions" aria-label="Acciones principales">
        <article>
          <div className="home-action-visual home-action-visual--map"><Map aria-hidden="true" /></div>
          <div><h2>Selecciona la zona donde quieres vivir</h2><p>Busca habitaciones en una o varias zonas directamente sobre el mapa.</p><Button asChild variant="outline"><Link to="/buscar?vista=mapa">Empezar a buscar</Link></Button></div>
        </article>
        <article>
          <div className="home-action-visual home-action-visual--publish"><Plus aria-hidden="true" /></div>
          <div><h2>Publica tu habitación</h2><p>Los primeros anuncios de habitaciones son gratuitos.</p><Button asChild><Link to="/publicar">Poner tu anuncio</Link></Button></div>
        </article>
      </section>

      <section className="home-results-preview">
        <div className="container">
          <div className="section-heading idealista-section-heading"><div><h2>Habitaciones destacadas en Tenerife</h2><p>Anuncios recientes de larga estancia y alquiler vacacional.</p></div><Button asChild variant="ghost"><Link to="/buscar">Ver todas <ArrowRight data-icon="inline-end" /></Link></Button></div>
          <div className="property-grid">{featured.map((listing) => <PropertyCard key={listing.id} listing={listing} compact />)}</div>
        </div>
      </section>

      <section className="container home-area-links">
        <div><h2>Alquiler de habitaciones por zona</h2><p>Encuentra una habitación cerca del trabajo, la universidad o la playa.</p></div>
        <div className="home-area-links__grid">{areas.map((area) => <Link key={area} to={`/buscar?q=${encodeURIComponent(area)}`}><span>Habitaciones en {area}</span><strong>{allListings.filter((listing) => listing.area === area).length}</strong></Link>)}</div>
      </section>

      <section className="home-alert-strip">
        <div className="container"><Bell aria-hidden="true" /><div><h2>¿Quieres enterarte antes?</h2><p>Guarda tu búsqueda y recibe avisos cuando aparezcan habitaciones nuevas.</p></div><Button asChild variant="outline"><Link to="/buscar">Crear una alerta</Link></Button></div>
      </section>
    </div>
  )
}
