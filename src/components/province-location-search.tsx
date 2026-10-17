import { useEffect, useMemo, useState } from 'react'
import { ChevronRight, Search, X } from 'lucide-react'
import { useApp } from '@/contexts/app-context'
import { api } from '@/api/client'
import { buildListingSearchBody } from '@/api/listings'
import { mobileHomeSearchFilters } from '@/lib/mobile-home-filters'
import { filterListings } from '@/lib/search'
import { listingInProvince, provinceSuggestions } from '@/lib/spain-provinces'
import type { Language } from '@/contexts/i18n-context'

export function ProvinceLocationSearch({ language, rentalMode, onSelect }: {
  language: Language; rentalMode: 'long' | 'holiday'; onSelect: (id: string) => void
}) {
  const { allListings, discarded, filters } = useApp()
  const [query, setQuery] = useState('')
  const [counts, setCounts] = useState<Record<string, number> | null>(null)
  const [error, setError] = useState(false)
  const suggestions = useMemo(() => provinceSuggestions(query), [query])
  const copy = {
    es: { placeholder: 'Buscar provincia', province: 'Provincia', empty: 'No se encontró ninguna provincia', listings: 'anuncios' },
    ru: { placeholder: 'Поиск провинции', province: 'Провинция', empty: 'Провинция не найдена', listings: 'объявлений' },
    en: { placeholder: 'Search province', province: 'Province', empty: 'No matching province', listings: 'listings' },
  }[language]
  useEffect(() => {
    const currentFilters = mobileHomeSearchFilters(filters, rentalMode)
    if (import.meta.env.VITE_ENABLE_MOCK_MODE === '1') {
      const eligible = filterListings(allListings.filter((listing) => !discarded.has(listing.id)), rentalMode, currentFilters)
      setCounts(Object.fromEntries(provinceSuggestions('').map((province) => [province.id, eligible.filter((listing) => listingInProvince(listing, province.id)).length])))
      return
    }
    const controller = new AbortController()
    setCounts(null); setError(false)
    void api<{ items: Array<{ id: string; count: number }> }>('/listings/provinces/counts', {
      method: 'POST', signal: controller.signal,
      body: JSON.stringify(buildListingSearchBody({ rentalMode, filters: currentFilters, minPrice: currentFilters.minPrice, maxPrice: currentFilters.maxPrice, query: 'España' })),
    }).then(({ items }) => { if (!controller.signal.aborted) setCounts(Object.fromEntries(items.map((entry) => [entry.id, entry.count]))) })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [allListings, discarded, filters, rentalMode])
  return <>
    <form className="m2-location-search" onSubmit={(event) => { event.preventDefault(); event.stopPropagation(); if (suggestions[0]) onSelect(suggestions[0].id) }}>
      <Search aria-hidden="true" /><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={copy.placeholder} aria-label={copy.placeholder} autoComplete="off" />
      {query ? <button type="button" className="m2-location-clear" aria-label={language === 'ru' ? 'Очистить' : language === 'en' ? 'Clear' : 'Limpiar'} onClick={() => setQuery('')}><X /></button> : null}
    </form>
    <div className="m2-community-suggestions" data-testid="province-suggestions">
      {suggestions.length ? suggestions.map((province) => <button type="button" className="m2-community-option" key={province.id} onClick={() => onSelect(province.id)} data-testid={`province-option-${province.id}`}>
        <span><strong>{province.es}</strong><small>{copy.province}</small></span>
        <span className="m2-community-option__count">{error ? '—' : counts ? counts[province.id] ?? 0 : '…'} {copy.listings}</span><ChevronRight />
      </button>) : <p className="m2-community-empty">{copy.empty}</p>}
    </div>
  </>
}
