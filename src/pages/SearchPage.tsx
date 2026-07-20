import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { Bell, ChevronRight, List, Map } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useApp } from '@/contexts/app-context'
import { EmptyState, ErrorState, FilterButton, FilterSidebar, getFilteredListings, LoadingSkeleton, MapView, Pagination, PropertyCard, RentalTypeSwitch, SearchBar } from '@/components/marketplace'

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const { rentalMode, filters, setFilters, query, saveCurrentSearch } = useApp()
  const [view, setView] = useState<'list' | 'map'>(params.get('vista') === 'mapa' ? 'map' : 'list')
  const [selected, setSelected] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  useEffect(() => { setView(params.get('vista') === 'mapa' ? 'map' : 'list') }, [params])
  const deferredFilters = useDeferredValue(filters)
  const baseItems = useMemo(() => getFilteredListings(rentalMode, deferredFilters), [rentalMode, deferredFilters])
  const items = useMemo(() => {
    const result = [...baseItems]
    if (filters.sort === 'Precio más bajo') result.sort((a, b) => a.price - b.price)
    if (filters.sort === 'Más recientes') result.sort((a, b) => b.views - a.views)
    return result
  }, [baseItems, filters.sort])
  const forcedState = params.get('estado')
  const changeView = (next: 'list' | 'map') => {
    setView(next)
    const updated = new URLSearchParams(params)
    if (next === 'map') updated.set('vista', 'mapa')
    else updated.delete('vista')
    setParams(updated)
  }
  const changeSort = (value: string) => {
    setLoading(true)
    setFilters({ ...filters, sort: value })
    window.setTimeout(() => setLoading(false), 260)
  }

  return (
    <div className="search-page idealista-search-page">
      <div className="search-toolbar"><div className="container"><RentalTypeSwitch compact /><SearchBar compact /></div></div>
      <div className="container search-breadcrumb"><Link to="/">Inicio</Link><ChevronRight aria-hidden="true" /><span>Habitaciones en {query || 'Tenerife'}</span></div>

      <div className={view === 'map' ? 'container idealista-results-layout is-map-view' : 'container idealista-results-layout'}>
        <FilterSidebar resultCount={items.length} />
        <section className="idealista-results" aria-labelledby="results-title">
          {params.get('alertas') === '1' ? <div className="search-alert-panel"><Bell aria-hidden="true" /><div><strong>Guarda esta búsqueda</strong><span>Te avisaremos cuando haya habitaciones nuevas en Tenerife.</span></div><Button onClick={() => { saveCurrentSearch(); setParams((current) => { const next = new URLSearchParams(current); next.delete('alertas'); return next }) }}>Guardar</Button></div> : null}
          <header className="results-head idealista-results-head"><div><h1 id="results-title">{items.length} habitaciones en alquiler en {query || 'Tenerife'}</h1><p>{rentalMode === 'long' ? 'Larga estancia' : 'Alquiler vacacional'}</p></div></header>
          <div className="idealista-results-toolbar">
            <div className="mobile-filter-control"><FilterButton resultCount={items.length} /></div>
            <label><span>Ordenar:</span><select value={filters.sort} onChange={(event) => changeSort(event.target.value)}><option>Relevancia</option><option>Más recientes</option><option>Precio más bajo</option></select></label>
            <Button variant={view === 'map' ? 'default' : 'outline'} onClick={() => changeView(view === 'map' ? 'list' : 'map')} aria-pressed={view === 'map'}>{view === 'map' ? <List data-icon="inline-start" /> : <Map data-icon="inline-start" />}{view === 'map' ? 'Lista' : 'Mapa'}</Button>
          </div>

          {view === 'map' ? <div className="idealista-map-view"><MapView items={items} selectedId={selected} onSelect={setSelected} fullScreen /></div> : forcedState === 'error' ? <ErrorState /> : forcedState === 'empty' || items.length === 0 ? <EmptyState /> : loading || forcedState === 'loading' ? <LoadingSkeleton /> : <div className="results-list">{items.map((listing) => <PropertyCard key={listing.id} listing={listing} selected={selected === listing.id} onFocus={() => setSelected(listing.id)} />)}<Pagination page={page} onPage={setPage} /></div>}
        </section>
      </div>
    </div>
  )
}
