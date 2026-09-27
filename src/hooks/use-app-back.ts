import { useCallback } from 'react'
import { useNavigate } from 'react-router'

/** Go to the previous router entry, or use a safe parent for a fresh deep link. */
export function useAppBack(fallback: string) {
  const navigate = useNavigate()
  return useCallback(() => {
    const index = (window.history.state as { idx?: unknown } | null)?.idx
    if (typeof index === 'number' && index > 0) navigate(-1)
    else navigate(fallback, { replace: true })
  }, [fallback, navigate])
}
