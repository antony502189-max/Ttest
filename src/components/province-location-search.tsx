import { useEffect, useId, useMemo, useState } from 'react'
import { ChevronRight, MapPin, Search, X } from 'lucide-react'
import { useApp } from '@/contexts/app-context'
import { api } from '@/api/client'
import { buildListingSearchBody } from '@/api/listings'
import { mobileHomeSearchFilters } from '@/lib/mobile-home-filters'
import { filterListings } from '@/lib/search'
import { listingInProvince, provinceSuggestions } from '@/lib/spain-provinces'
import { listingInMunicipality, locationSuggestions, rememberPlace, recentPlaces, placeProvinceName } from '@/lib/spain-locations'
import type { Language } from '@/contexts/i18n-context'

export function ProvinceLocationSearch({ language, rentalMode, onSelect, desktop = false }: {
  desktop?: boolean; language: Language; rentalMode: 'long' | 'holiday'; onSelect: (id: string) => void
}) {
  const { allListings, discarded, filters } = useApp()
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const [counts, setCounts] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState(false)
  const [recent] = useState(recentPlaces)
  const [active, setActive] = useState(-1)
  const listId = useId()
  const suggestions = useMemo(() => locationSuggestions(query, recent), [query, recent])
  const select = (id: string) => { rememberPlace(id); onSelect(id) }
  const copy = {
    es: { placeholder: 'Buscar provincia o municipio', province: 'Provincia', municipality: 'Municipio', empty: 'No se encontró ninguna ubicación', listings: 'anuncios' },
    ru: { placeholder: 'Поиск провинции или муниципалитета', province: 'Провинция', municipality: 'Муниципалитет', empty: 'Место не найдено', listings: 'объявлений' },
    en: { placeholder: 'Search province or municipality', province: 'Province', municipality: 'Municipality', empty: 'No matching location', listings: 'listings' },
  }[language]
  const countLabel = (count: number | undefined) => {
    if (count === undefined) return `${error ? '—' : '…'} ${copy.listings}`
    const category = new Intl.PluralRules(language).select(count)
    const noun = language === 'ru'
      ? category === 'one' ? 'объявление' : category === 'few' ? 'объявления' : copy.listings
      : category === 'one' ? language === 'es' ? 'anuncio' : 'listing' : copy.listings
    return `${new Intl.NumberFormat(language).format(count)} ${noun}`
  }
  useEffect(() => {
    if (import.meta.env.VITE_ENABLE_MOCK_MODE !== '1') return
    const currentFilters = mobileHomeSearchFilters(filters, rentalMode)
    const eligible = filterListings(allListings.filter((listing) => !discarded.has(listing.id)), rentalMode, currentFilters)
    setCounts(Object.fromEntries([
      ...provinceSuggestions('').map((province) => [province.id, eligible.filter((listing) => listingInProvince(listing, province.id)).length]),
      ...suggestions.filter((place) => place.type === 'municipality').map((place) => [place.id, eligible.filter((listing) => listingInMunicipality(listing, place.id)).length]),
    ]))
  }, [allListings, discarded, filters, rentalMode, suggestions])
  useEffect(() => {
    if (import.meta.env.VITE_ENABLE_MOCK_MODE === '1') return
    const currentFilters = mobileHomeSearchFilters(filters, rentalMode)
    const controller = new AbortController()
    setCounts(null); setError(false)
    void api<{ items: Array<{ id: string; count: number }>; municipalities: Array<{ id: string; count: number }> }>('/listings/locations/counts', {
      method: 'POST', signal: controller.signal,
      body: JSON.stringify(buildListingSearchBody({ rentalMode, filters: currentFilters, minPrice: currentFilters.minPrice, maxPrice: currentFilters.maxPrice, query: 'España' })),
    }).then(({ items, municipalities }) => { if (!controller.signal.aborted) setCounts(Object.fromEntries([...items, ...municipalities].map((entry) => [entry.id, entry.count]))) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [allListings, discarded, filters, rentalMode])
  return <>
    <form className={desktop ? "location-selector-search" : "m2-location-search"} onSubmit={(event) => { event.preventDefault(); event.stopPropagation(); const place = suggestions[active < 0 ? 0 : active]; if (place) select(place.id) }}>
      <Search aria-hidden="true" /><input type="search" value={query} onFocus={() => setFocused(true)} onChange={(event) => { setQuery(event.target.value); setActive(-1) }} placeholder={copy.placeholder} aria-label={copy.placeholder} autoComplete="off"
        aria-controls={desktop || focused ? listId : undefined}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault()
            const next = Math.max(0, Math.min(suggestions.length - 1, active + (event.key === 'ArrowDown' ? 1 : -1)))
            setActive(next)
            document.getElementById(`${listId}-${suggestions[next]?.id}`)?.scrollIntoView({ block: 'nearest' })
          }
          if (event.key === 'Escape') { setFocused(false); setActive(-1) }
        }} />
      {query ? <button type="button" className="m2-location-clear" aria-label={language === 'ru' ? 'Очистить' : language === 'en' ? 'Clear' : 'Limpiar'} onClick={() => { setQuery(''); setActive(-1) }}><X /></button> : null}
    </form>
    {(desktop || focused) && <div id={listId} className={desktop ? "location-catalog-list location-province-list" : "m2-community-suggestions"} data-testid="province-suggestions">
      {suggestions.length ? suggestions.map((province) => <button type="button" id={`${listId}-${province.id}`} className={desktop ? "location-province-option" : "m2-community-option"} key={province.id} onClick={() => select(province.id)} data-testid={`${province.type}-option-${province.id}`} style={suggestions[active]?.id === province.id ? { outline: '2px solid currentColor', outlineOffset: '-2px' } : undefined}>
        {desktop ? <MapPin aria-hidden="true" /> : null}
        <span><strong>{province.label}</strong><small>{province.type === 'province' ? copy.province : `${copy.municipality} · ${placeProvinceName(province)}`}</small></span>
        <span className="m2-community-option__count">{countLabel(error || !counts ? undefined : counts[province.id] ?? 0)}</span><ChevronRight />
      </button>) : <p className="m2-community-empty">{copy.empty}</p>}
    </div>}
  </>
}
