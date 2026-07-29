import { useLayoutEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import './obsolete-phone-search-removal.css'

export function ObsoletePhoneSearchRemoval() {
  const location = useLocation()
  const navigate = useNavigate()

  useLayoutEffect(() => {
    if (location.pathname === '/' && new URLSearchParams(location.search).get('panel') === 'telefono') {
      navigate('/?panel=ubicacion', { replace: true })
      return
    }

    const removePhoneSearch = () => {
      document.querySelectorAll('[data-testid="search-phone"]').forEach((element) => element.remove())
    }

    removePhoneSearch()
    const observer = new MutationObserver(removePhoneSearch)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [location.pathname, location.search, navigate])

  return null
}
