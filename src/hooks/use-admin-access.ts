import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { checkAdminAccess } from '@/api/admin'
import { useApp } from '@/contexts/app-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

/**
 * UI-only projection of the server admin authorization decision.
 *
 * Production never derives administration visibility from the product role.
 * The protected route and every admin endpoint still authorize independently
 * on the server; this hook only decides whether to expose navigation.
 */
export function useAdminAccess() {
  const { currentUser } = useApp()
  const { pathname } = useLocation()
  const [allowed, setAllowed] = useState(false)

  useEffect(() => {
    if (!currentUser) {
      setAllowed(false)
      return
    }
    if (mockMode) {
      setAllowed(currentUser.role === 'admin')
      return
    }

    let cancelled = false
    const refresh = () => {
      void checkAdminAccess()
        .then(() => { if (!cancelled) setAllowed(true) })
        .catch(() => { if (!cancelled) setAllowed(false) })
    }

    refresh()
    window.addEventListener('focus', refresh)
    return () => {
      cancelled = true
      window.removeEventListener('focus', refresh)
    }
  }, [currentUser?.id, currentUser?.role, pathname])

  return allowed
}
