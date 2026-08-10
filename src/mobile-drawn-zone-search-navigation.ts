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
  params.delete('dibujar')
  params.delete('pagina')
  params.delete('panel')
  window.location.hash = `/buscar?${params.toString()}`
}

document.addEventListener('click', handleDrawnZoneSearch, true)
