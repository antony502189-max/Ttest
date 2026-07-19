import { useDeferredValue, useMemo, useState } from 'react'
import { List, Map, SlidersHorizontal } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useApp } from '@/contexts/app-context'
import { EmptyState, ErrorState, getFilteredListings, LoadingSkeleton, MapView, Pagination, PropertyCard, QuickFilters, RentalTypeSwitch, SearchBar } from '@/components/marketplace'

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const { rentalMode, filters, setFilters, query } = useApp()
  const [view, setView] = useState<'list' | 'map'>(params.get('vista') === 'mapa' ? 'map' : 'list')
  const [selected, setSelected] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const deferredFilters = useDeferredValue(filters)
  const baseItems = useMemo(() => getFilteredListings(rentalMode, deferredFilters), [rentalMode, deferredFilters])
  const items = useMemo(() => {
    const result = [...baseItems]
    if (filters.sort === 'Precio más bajo') result.sort((a, b) => a.price - b.price)
    if (filters.sort === 'Más recientes') result.sort((a, b) => b.views - a.views)
    return result
  }, [baseItems, filters.sort])
  const forcedState = params.get('estado')
  const changeView = (next: 'list' | 'map') => { setView(next); const updated = new URLSearchParams(params); if (next === 'map') updated.set('vista', 'mapa'); else updated.delete('vista'); setParams(updated) }
  const changeSort = (value: string) => { setLoading(true); setFilters({ ...filters, sort: value }); window.setTimeout(() => setLoading(false), 260) }

  return (
    <div className="search-page">
      <div className="search-toolbar">
        <div className="container"><RentalTypeSwitch compact /><SearchBar compact /></div>
      </div>
      <div className="filters-toolbar">
        <div className="container"><QuickFilters resultCount={items.length} /><div className="view-switch" role="group" aria-label="Vista de resultados"><Button variant={view === 'list' ? 'default' : 'outline'} onClick={() => changeView('list')} aria-pressed={view === 'list'}><List data-icon="inline-start" />Lista</Button><Button variant={view === 'map' ? 'default' : 'outline'} onClick={() => changeView('map')} aria-pressed={view === 'map'}><Map data-icon="inline-start" />Mapa</Button></div></div>
      </div>
      <div className="search-split">
        <section className={view === 'map' ? 'results-column is-mobile-hidden' : 'results-column'} aria-labelledby="results-title">
          <div className="results-head"><div><p className="eyebrow">{rentalMode === 'long' ? 'Larga estancia' : 'Alquiler vacacional'}</p><h1 id="results-title">Habitaciones en {query || 'Tenerife'}</h1><p aria-live="polite">{items.length} anuncios encontrados</p></div><label>Ordenar por<select value={filters.sort} onChange={(event) => changeSort(event.target.value)}><option>Relevancia</option><option>Más recientes</option><option>Precio más bajo</option></select></label></div>
          {forcedState === 'error' ? <ErrorState /> : forcedState === 'empty' || items.length === 0 ? <EmptyState /> : loading || forcedState === 'loading' ? <LoadingSkeleton /> : <div className="results-list">{items.map((listing) => <PropertyCard key={listing.id} listing={listing} selected={selected === listing.id} onFocus={() => setSelected(listing.id)} />)}<Pagination page={page} onPage={setPage} /></div>}
        </section>
        <div className={view === 'list' ? 'map-column is-mobile-hidden' : 'map-column'}><MapView items={items} selectedId={selected} onSelect={setSelected} fullScreen={view === 'map'} /></div>
      </div>
      <div className="mobile-view-toggle"><Button onClick={() => changeView(view === 'list' ? 'map' : 'list')}><span>{view === 'list' ? <Map /> : <List />}</span>{view === 'list' ? 'Ver mapa' : 'Ver lista'}</Button><Button variant="outline" onClick={() => document.querySelector<HTMLButtonElement>('.quick-filters button:last-of-type')?.click()} aria-label="Abrir filtros"><SlidersHorizontal /></Button></div>
    </div>
  )
}
