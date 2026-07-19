import { ArrowRight, BadgeCheck, DoorOpen, MapPinned, MessageCircle, SearchCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { areas, listings } from '@/data/listings'
import { FeatureIcon, PropertyCard, RentalTypeSwitch, SearchBar } from '@/components/marketplace'

const areaCounts: Record<string, number> = { 'Costa Adeje': 24, 'Armeñime': 12, 'Playa de las Américas': 19, 'Los Cristianos': 31, 'San Isidro': 17, 'El Médano': 15, 'Santa Cruz de Tenerife': 68, 'La Laguna': 74 }

export function HomePage() {
  return (
    <div className="home-page">
      <section className="search-hero">
        <div className="container search-hero__inner">
          <div className="hero-kicker"><DoorOpen />Solo habitaciones · Tenerife</div>
          <h1>Encuentra una habitación que encaje contigo.</h1>
          <p>Precio, gastos y condiciones de convivencia claros antes de contactar.</p>
          <RentalTypeSwitch />
          <SearchBar />
          <div className="hero-meta"><span><BadgeCheck />Anuncios revisados</span><span><MapPinned />Ubicación aproximada</span><span><MessageCircle />Contacto directo</span></div>
        </div>
      </section>

      <section className="section container">
        <div className="section-heading"><div><span className="eyebrow">Explora por zona</span><h2>Habitaciones donde quieres vivir</h2></div><Button asChild variant="ghost"><Link to="/buscar">Ver todas <ArrowRight data-icon="inline-end" /></Link></Button></div>
        <div className="area-grid">{areas.map((area, index) => <Link key={area} to={`/buscar?q=${encodeURIComponent(area)}`} className={index < 2 ? 'area-card area-card--wide' : 'area-card'}><span>{String(index + 1).padStart(2, '0')}</span><strong>{area}</strong><small>{areaCounts[area]} habitaciones</small><ArrowRight /></Link>)}</div>
      </section>

      <section className="section section--surface">
        <div className="container">
          <div className="section-heading"><div><span className="eyebrow">Recién publicadas</span><h2>Nuevas habitaciones</h2></div><Button asChild variant="outline"><Link to="/buscar">Ver resultados</Link></Button></div>
          <div className="property-grid">{listings.slice(0, 3).map((listing) => <PropertyCard key={listing.id} listing={listing} compact />)}</div>
        </div>
      </section>

      <section className="section container">
        <div className="split-intro"><div><span className="eyebrow">El foco importa</span><h2>No vendemos pisos. No mostramos oficinas. Solo habitaciones.</h2></div><div><p>112233.es organiza la información que de verdad afecta a una convivencia: quién vive en casa, duración mínima, gastos, fianza, mascotas, tabaco y empadronamiento.</p><Button asChild><Link to="/como-funciona">Cómo funciona <ArrowRight data-icon="inline-end" /></Link></Button></div></div>
        <div className="features-grid"><FeatureIcon icon={SearchCheck} title="Compara sin abrir diez pestañas">Las condiciones importantes aparecen en cada tarjeta.</FeatureIcon><FeatureIcon icon={BadgeCheck} title="Información estructurada">Precio, fianza y gastos no se esconden en la descripción.</FeatureIcon><FeatureIcon icon={MessageCircle} title="Habla directamente">WhatsApp, teléfono o mensaje interno, tú eliges.</FeatureIcon></div>
      </section>

      <section className="section container">
        <div className="owner-banner"><div><span className="eyebrow">¿Tienes una habitación libre?</span><h2>Publícala paso a paso.</h2><p>Un anuncio completo recibe contactos más compatibles y ahorra conversaciones innecesarias.</p></div><Button asChild size="lg"><Link to="/publicar">Publicar habitación <ArrowRight data-icon="inline-end" /></Link></Button></div>
      </section>
    </div>
  )
}
