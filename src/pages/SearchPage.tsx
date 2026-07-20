import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { Bell, CalendarDays, ChevronRight, Heart, List, Map, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useApp } from '@/contexts/app-context'
import { areas } from '@/data/listings'
import { EmptyState, ErrorState, FilterButton, FilterSidebar, getFilteredListings, LoadingSkeleton, MapView, Pagination, PropertyCard, QuickFilters, RentalTypeSwitch, SearchBar } from '@/components/marketplace'

export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const { rentalMode, filters, setFilters, resetFilters, query, setQuery, saveCurrentSearch, activeFilterCount } = useApp()
  const [view, setView] = useState<'list' | 'map'>(params.get('vista') === 'mapa' ? 'map' : 'list')
  const [selected, setSelected] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const urlQuery = params.get('q')?.trim() || ''
  const urlAreas = params.get('zonas')?.split('|').filter(Boolean) ?? []
  const urlAreasKey = urlAreas.join('|')
  useEffect(() => { setView(params.get('vista') === 'mapa' ? 'map' : 'list') }, [params])
  useEffect(() => {
    if (urlQuery && urlQuery !== query) setQuery(urlQuery)
  }, [query, setQuery, urlQuery])
  useEffect(() => {
    const exactArea = areas.find((area) => area.toLocaleLowerCase() === urlQuery.toLocaleLowerCase())
    const nextAreas = urlAreas.length ? urlAreas : exactArea ? [exactArea] : []
    if (urlQuery && JSON.stringify(nextAreas) !== JSON.stringify(filters.areas)) setFilters({ ...filters, areas: nextAreas })
    // URL changes are the source of truth when the user opens a new search.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlAreasKey, urlQuery])
  const deferredFilters = useDeferredValue(filters)
  const baseItems = useMemo(() => getFilteredListings(rentalMode, deferredFilters), [rentalMode, deferredFilters])
  const items = useMemo(() => {
    const result = [...baseItems]
    if (filters.sort === 'Precio más bajo') result.sort((a, b) => a.price - b.price)
    if (filters.sort === 'Más recientes') result.sort((a, b) => b.views - a.views)
    return result
  }, [baseItems, filters.sort])
  const forcedState = params.get('estado')
  const moveDate = params.get('fecha')
  const formattedDate = moveDate ? new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'short' }).format(new Date(`${moveDate}T12:00:00`)) : 'Cualquier fecha'
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
    const updated = new URLSearchParams(params)
    if (value === 'Relevancia') updated.delete('orden')
    else updated.set('orden', value === 'Más recientes' ? 'recientes' : 'precio')
    setParams(updated)
    window.setTimeout(() => setLoading(false), 260)
  }
  const clearAll = () => {
    resetFilters()
    const updated = new URLSearchParams(params)
    updated.delete('zonas')
    setParams(updated)
  }
  const appliedFilters = [
    filters.areas.length ? { key: 'areas', label: filters.areas.length === 1 ? filters.areas[0] : `${filters.areas.length} zonas`, clear: () => setFilters({ ...filters, areas: [] }) } : null,
    filters.minPrice || filters.maxPrice < 1000 ? { key: 'price', label: `${filters.minPrice}–${filters.maxPrice >= 1000 ? '1.000+' : filters.maxPrice} €`, clear: () => setFilters({ ...filters, minPrice: 0, maxPrice: 1000 }) } : null,
    filters.roomType !== 'Cualquiera' ? { key: 'room', label: filters.roomType, clear: () => setFilters({ ...filters, roomType: 'Cualquiera' }) } : null,
    filters.bathroom !== 'Cualquiera' ? { key: 'bath', label: filters.bathroom, clear: () => setFilters({ ...filters, bathroom: 'Cualquiera' }) } : null,
    filters.billsIncluded ? { key: 'bills', label: 'Gastos incluidos', clear: () => setFilters({ ...filters, billsIncluded: false }) } : null,
    ...filters.conditions.map((condition) => ({ key: `condition-${condition}`, label: condition, clear: () => setFilters({ ...filters, conditions: filters.conditions.filter((item) => item !== condition) }) })),
  ].filter(Boolean) as { key: string; label: string; clear: () => void }[]

  return (
    <div className={view === 'map' ? 'search-page idealista-search-page is-map-page' : 'search-page idealista-search-page'}>
      <div className="search-toolbar"><div className="container"><RentalTypeSwitch compact /><SearchBar compact /></div></div>
      <div className="container search-breadcrumb"><Link to="/">Inicio</Link><ChevronRight aria-hidden="true" /><span>Habitaciones en {query || 'Tenerife'}</span></div>

      <div className={view === 'map' ? 'container idealista-results-layout is-map-view' : 'container idealista-results-layout'}>
        <FilterSidebar resultCount={items.length} />
        <section className="idealista-results" aria-labelledby="results-title">
          {params.get('alertas') === '1' ? <div className="search-alert-panel"><Bell aria-hidden="true" /><div><strong>Guarda esta búsqueda</strong><span>Te avisaremos cuando haya habitaciones nuevas en Tenerife.</span></div><Button onClick={() => { saveCurrentSearch(); setParams((current) => { const next = new URLSearchParams(current); next.delete('alertas'); return next }) }}>Guardar</Button></div> : null}
          <header className="results-head idealista-results-head"><div><h1 id="results-title">{items.length} habitaciones en alquiler en {query || 'Tenerife'}</h1><p><CalendarDays aria-hidden="true" />{formattedDate} · {rentalMode === 'long' ? 'Larga estancia' : 'Alquiler vacacional'} <button type="button" onClick={() => document.querySelector<HTMLInputElement>('.search-toolbar input')?.focus()}>Modificar</button></p></div><Button variant="outline" className="save-search-button" onClick={saveCurrentSearch}><Heart data-icon="inline-start" />Guardar búsqueda</Button></header>
          <QuickFilters resultCount={items.length} />
          {appliedFilters.length ? <div className="applied-filters" aria-label="Filtros aplicados">{appliedFilters.map((filter) => <button type="button" key={filter.key} onClick={filter.clear}>{filter.label}<X aria-hidden="true" /></button>)}<button type="button" className="applied-filters__clear" onClick={clearAll}>Borrar filtros ({activeFilterCount})</button></div> : null}
          <div className="idealista-results-toolbar">
            <div className="mobile-filter-control"><FilterButton resultCount={items.length} /></div>
            <label><span>Ordenar:</span><select aria-label="Ordenar resultados" value={filters.sort} onChange={(event) => changeSort(event.target.value)}><option>Relevancia</option><option>Más recientes</option><option>Precio más bajo</option></select></label>
            <Button variant={view === 'map' ? 'default' : 'outline'} onClick={() => changeView(view === 'map' ? 'list' : 'map')} aria-pressed={view === 'map'}>{view === 'map' ? <List data-icon="inline-start" /> : <Map data-icon="inline-start" />}{view === 'map' ? 'Lista' : 'Mapa'}</Button>
          </div>

          {view === 'map' ? <div className="idealista-map-view"><MapView items={items} selectedId={selected} onSelect={setSelected} fullScreen /></div> : forcedState === 'error' ? <ErrorState /> : forcedState === 'empty' || items.length === 0 ? <EmptyState /> : loading || forcedState === 'loading' ? <LoadingSkeleton /> : <div className="results-list">{items.map((listing) => <PropertyCard key={listing.id} listing={listing} selected={selected === listing.id} onFocus={() => setSelected(listing.id)} />)}<Pagination page={page} onPage={setPage} /><section className="search-related" aria-labelledby="related-title"><h2 id="related-title">También puede interesarte</h2><div><Link to="/registro">Publica tu perfil para que te encuentren</Link><Link to="/buscar?q=Adeje">Habitaciones en Adeje</Link><Link to="/buscar?q=Arona">Habitaciones en Arona</Link><Link to="/buscar?q=La%20Laguna">Habitaciones en La Laguna</Link></div></section></div>}
        </section>
      </div>
      <Button className="mobile-map-toggle" onClick={() => changeView(view === 'map' ? 'list' : 'map')} aria-label={view === 'map' ? 'Mostrar lista de habitaciones' : 'Mostrar habitaciones en el mapa'}>{view === 'map' ? <List data-icon="inline-start" /> : <Map data-icon="inline-start" />}{view === 'map' ? 'Ver lista' : 'Ver mapa'}</Button>
    </div>
  )
}
