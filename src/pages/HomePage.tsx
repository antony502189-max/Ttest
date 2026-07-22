import { ArrowRight, CigaretteOff, Clock3, Heart, Map, MessageCircle, PawPrint, Plus, Search, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { PropertyCard, RentalTypeSwitch, SearchBar } from '@/components/marketplace'
import { useApp, type SavedSearch } from '@/contexts/app-context'
import { MediaImage } from '@/components/media-image'
import { filterListings, filtersToParams } from '@/lib/search'
import { isPublicListing, tenantRequirementLabels } from '@/lib/listings'
import '@/home.css'

const homeHeroImage = 'https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=1920&q=88'

const searchHref = (search: SavedSearch) => `/buscar?${filtersToParams(search.filters, new URLSearchParams({ q: search.query, alquiler: search.rentalMode })).toString()}`

function TenerifeMapPreview() {
  return <svg className="tenerife-outline" viewBox="0 0 360 190" role="img" aria-label="Silueta ilustrada de Tenerife">
    <path className="tenerife-outline__roads" d="M38 130C88 112 111 91 150 83s72-3 108-22m-174 71c40 3 72 12 106 6 38-7 69-31 106-52M121 110l-5-62m78 65 25-76" />
    <path className="tenerife-outline__island" d="M21 137c27-14 42-32 60-49 21-20 41-31 69-34 33-3 57-21 92-27 25-4 49 7 76 15-18 10-31 25-48 38-23 18-50 24-78 37-26 12-50 30-80 36-33 7-62-2-91-16Z" />
    <circle cx="83" cy="116" r="5" /><circle cx="151" cy="82" r="5" /><circle cx="244" cy="61" r="5" /><circle cx="287" cy="49" r="5" />
  </svg>
}

export function HomePage() {
  const { allListings, savedSearches } = useApp()
  const publicListings = allListings.filter(isPublicListing)
  const featured = publicListings.slice(0, 2)
  return (
    <div className="home-page market-home">
      <section className="home-hero" aria-labelledby="home-title">
        <MediaImage src={homeHeroImage} alt="Habitación luminosa con cama, escritorio y ventana" width="1920" height="1080" />
        <div className="home-hero__overlay" />
        <div className="home-hero__content">
          <h1 id="home-title">Solo habitaciones</h1>
          <p>Larga estancia y turística</p>
          <div className="home-hero__chips" aria-label="Condiciones habituales">
            <Badge variant="secondary" className="hero-condition-chip"><PawPrint aria-hidden="true" />Sin mascotas</Badge>
            <Badge variant="secondary" className="hero-condition-chip"><CigaretteOff aria-hidden="true" />No fumar</Badge>
          </div>
        </div>
      </section>

      <section className="home-search-stage" aria-label="Buscar habitaciones">
        <Card className="market-search-panel">
          <CardHeader className="sr-only">
            <CardTitle>Encuentra una habitación</CardTitle>
            <CardDescription>Elige el tipo de alquiler, quién vivirá y la zona.</CardDescription>
          </CardHeader>
          <CardContent className="market-search-panel__content">
            <RentalTypeSwitch home />
            <SearchBar home />
          </CardContent>
        </Card>
        <div className="home-trust-strip" aria-label="Ventajas de 112233.es">
          <div><ShieldCheck aria-hidden="true" /><span>Anuncios verificados</span></div>
          <Separator orientation="vertical" />
          <div><Heart aria-hidden="true" /><span>Guarda tus favoritos</span></div>
          <Separator orientation="vertical" />
          <div><MessageCircle aria-hidden="true" /><span>Contacta sin comisión</span></div>
        </div>
      </section>

      <div className="home-publish-action"><Button asChild variant="outline"><Link to="/publicar"><Plus data-icon="inline-start" />Publicar anuncio</Link></Button></div>

      <section className="container home-saved-searches" aria-labelledby="saved-searches-title">
        <div className="market-section-heading"><div><span className="eyebrow">Vuelve donde lo dejaste</span><h2 id="saved-searches-title">Tus búsquedas</h2></div><Button asChild variant="ghost"><Link to="/busquedas-guardadas">Ver todas <ArrowRight data-icon="inline-end" /></Link></Button></div>
        {savedSearches.length ? <div className="home-search-list">{savedSearches.slice(0, 2).map((saved) => {
          const count = filterListings(publicListings, saved.rentalMode, saved.filters).length
          const tenant = saved.filters.tenantRequirement === 'Cualquiera' ? 'Cualquiera' : tenantRequirementLabels[saved.filters.tenantRequirement]
          return <Link to={searchHref(saved)} key={saved.id}><Search aria-hidden="true" /><span><strong>{saved.query || 'Tenerife'}</strong><small>{saved.rentalMode === 'long' ? 'Habitaciones Vivienda' : 'Habitaciones Turísticas'} · {tenant}</small></span><span><b>{count}</b><small>resultados</small></span><ArrowRight aria-hidden="true" /></Link>
        })}</div> : <div className="home-search-empty"><Search aria-hidden="true" /><div><strong>Aún no tienes búsquedas guardadas</strong><p>Aplica tus condiciones y guárdalas desde los resultados.</p></div><Button asChild variant="outline"><Link to="/buscar">Nueva búsqueda</Link></Button></div>}
      </section>

      <section className="container home-map-section" aria-labelledby="map-section-title">
        <div className="home-map-visual"><TenerifeMapPreview /></div>
        <div><span className="eyebrow">Tenerife por zonas</span><h2 id="map-section-title">Seleccionar zonas en el mapa</h2><p>Busca en varios municipios o dibuja el área que te interesa.</p><Button asChild><Link to="/buscar?vista=mapa"><Map data-icon="inline-start" />Abrir mapa</Link></Button></div>
      </section>

      <section className="home-results-preview">
        <div className="container">
          <div className="market-section-heading"><div><span className="eyebrow">Publicadas recientemente</span><h2>Habitaciones destacadas</h2></div><Button asChild variant="ghost"><Link to="/buscar">Ver todas <ArrowRight data-icon="inline-end" /></Link></Button></div>
          <div className="home-featured-list">{featured.map((listing) => <PropertyCard key={listing.id} listing={listing} compact />)}</div>
          <p className="home-freshness"><Clock3 aria-hidden="true" />Precios, disponibilidad y condiciones visibles antes de contactar.</p>
        </div>
      </section>
    </div>
  )
}
