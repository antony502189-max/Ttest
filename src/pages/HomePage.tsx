import { ArrowRight, Clock3, Map, Plus, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PropertyCard, RentalTypeSwitch, SearchBar } from '@/components/marketplace'
import { useApp, type SavedSearch } from '@/contexts/app-context'
import { MediaImage } from '@/components/media-image'
import { filterListings, filtersToParams } from '@/lib/search'
import { isPublicListing, tenantRequirementLabels } from '@/lib/listings'

interface FeaturedPlacement {
  listingId: string
  active: boolean
  label: 'Destacado' | 'Publicidad'
  priority: number
}

const searchHref = (search: SavedSearch) => `/buscar?${filtersToParams(search.filters, new URLSearchParams({ q: search.query, alquiler: search.rentalMode })).toString()}`

export function HomePage() {
  const { allListings, savedSearches } = useApp()
  const publicListings = allListings.filter(isPublicListing)
  const featured = publicListings.slice(0, 2)
  const placement: FeaturedPlacement = { listingId: publicListings[1]?.id ?? publicListings[0]?.id ?? '', active: true, label: 'Destacado', priority: 1 }
  const promoted = publicListings.find((listing) => listing.id === placement.listingId) ?? publicListings[0]
  return (
    <div className="home-page market-home">
      <h1 id="home-title" className="sr-only">Tu próxima habitación está más cerca de lo que imaginas</h1>
      {promoted && placement.active ? <Link className="promoted-listing" to={`/habitacion/${promoted.id}`} aria-label={`Ver anuncio destacado: ${promoted.title}`}>
        <MediaImage src={promoted.images[0]} alt={`Habitación destacada en ${promoted.area}`} width="1600" height="900" />
        <span className="promoted-listing__label">{placement.label}</span>
        <span className="promoted-listing__caption"><strong>{promoted.area}</strong><span>{promoted.monthlyPrice || promoted.nightlyPrice} €/{promoted.rentalMode === 'holiday' ? 'noche' : 'mes'}</span></span>
      </Link> : null}

      <section className="market-search-panel" aria-label="Buscar habitaciones">
        <RentalTypeSwitch />
        <SearchBar home />
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
        <div className="home-map-visual" aria-hidden="true"><span /><Map /></div>
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
