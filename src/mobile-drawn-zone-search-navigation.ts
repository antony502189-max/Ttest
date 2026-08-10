function currentHashSearch() {
  const route = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash
  const queryIndex = route.indexOf('?')
  return {
    pathname: queryIndex >= 0 ? route.slice(0, queryIndex) : route,
    params: new URLSearchParams(queryIndex >= 0 ? route.slice(queryIndex + 1) : ''),
  }
}

function handleDrawnZoneSearch(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element)) return
  if (!target.closest('[data-testid="search-this-area"]')) return

  const { pathname, params } = currentHashSearch()
  if (pathname !== '/buscar' || !params.has('poligono')) return

  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()
  // A completed draw session remains on the map so the user can inspect the
  // resulting polygon.  An already-existing polygon's search action instead
  // opens its listing results, which is the normal search-area affordance.
  const keepMap = params.get('dibujar') === '1'
  params.delete('dibujar')
  if (!keepMap) params.delete('vista')
  params.delete('pagina')
  params.delete('panel')
  window.location.hash = `/buscar?${params.toString()}`
}

document.addEventListener('click', handleDrawnZoneSearch, true)
