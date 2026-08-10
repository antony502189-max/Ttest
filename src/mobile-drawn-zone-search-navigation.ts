import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'

export function MobileDrawnZoneSearchNavigation() {
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (location.pathname !== '/buscar') return

    const handleSearchArea = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest<HTMLElement>('[data-testid="search-this-area"]')
      if (!button) return

      const params = new URLSearchParams(location.search)
      if (!params.has('poligono')) return

      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation()
      params.delete('dibujar')
      params.delete('vista')
      params.delete('pagina')
      params.delete('panel')
      navigate(`/buscar?${params.toString()}`)
    }

    document.addEventListener('click', handleSearchArea, true)
    return () => document.removeEventListener('click', handleSearchArea, true)
  }, [location.pathname, location.search, navigate])

  return null
}
