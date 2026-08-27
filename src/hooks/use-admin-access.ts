import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { checkAdminAccess } from '@/api/admin'
import { ApiError } from '@/api/client'
import { useApp } from '@/contexts/app-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

/**
 * UI-only projection of the server admin authorization decision.
 *
 * Production never derives administration visibility from the product role.
 * The protected route and every admin endpoint still authorize independently
 * on the server; this hook only decides whether to expose navigation.
 */
export type AdminAccessState = 'allowed' | 'denied' | 'google_identity_required'

export function useAdminAccessState(): AdminAccessState {
  const { currentUser } = useApp()
  const { pathname } = useLocation()
  const [state, setState] = useState<AdminAccessState>('denied')
  const userId = currentUser?.id
  const productRole = currentUser?.role

  useEffect(() => {
    if (!userId) {
      setState('denied')
      return
    }
    if (mockMode) {
      setState(productRole === 'admin' ? 'allowed' : 'denied')
      return
    }

    let cancelled = false
    const refresh = () => {
      void checkAdminAccess()
        .then(() => { if (!cancelled) setState('allowed') })
        .catch((error: unknown) => {
          if (!cancelled) setState(error instanceof ApiError && error.code === 'GOOGLE_IDENTITY_REQUIRED' ? 'google_identity_required' : 'denied')
        })
    }

    refresh()
    window.addEventListener('focus', refresh)
    return () => {
      cancelled = true
      window.removeEventListener('focus', refresh)
    }
  }, [pathname, productRole, userId])

  return state
}

export function useAdminAccess() {
  return useAdminAccessState() === 'allowed'
}
