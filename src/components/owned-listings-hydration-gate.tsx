import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getOwnedListings } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const PROVIDER_SYNC_TIMEOUT_MS = 8_000

type Phase = 'checking' | 'syncing' | 'ready' | 'error'

const copy: Record<Language, { loading: string; help: string; error: string; errorHelp: string; retry: string }> = {
  es: {
    loading: 'Cargando tus anuncios…',
    help: 'Estamos sincronizando la lista actual con el servidor.',
    error: 'No pudimos cargar tus anuncios',
    errorHelp: 'Tus anuncios no se han borrado. Reintenta la sincronización.',
    retry: 'Reintentar',
  },
  en: {
    loading: 'Loading your listings…',
    help: 'We are syncing the current list with the server.',
    error: 'We could not load your listings',
    errorHelp: 'Your listings have not been deleted. Retry the sync.',
    retry: 'Retry',
  },
  ru: {
    loading: 'Загружаем ваши объявления…',
    help: 'Синхронизируем актуальный список с сервером.',
    error: 'Не удалось загрузить ваши объявления',
    errorHelp: 'Объявления не удалены. Повторите синхронизацию.',
    retry: 'Повторить',
  },
}

/**
 * `/listings/mine` is authoritative for the owner page. The provider starts
 * with an empty array while its request is in flight, so rendering the normal
 * empty state at that point makes real listings appear to have been deleted.
 *
 * This gate never substitutes its own listing snapshot into AppContext:
 * provider action callbacks and edit routes must see the same authoritative
 * state as the cards. A non-empty probe therefore triggers the provider's
 * existing refresh path and keeps the route in a syncing state until the
 * provider itself has hydrated `ownedListings`.
 */
export function OwnedListingsHydrationGate({ children }: { children: ReactNode }) {
  const app = useApp()
  const { language } = useI18n()
  const text = copy[language]
  const userId = app.currentUser?.id ?? null
  const [phase, setPhase] = useState<Phase>(() => mockMode || app.ownedListings.length ? 'ready' : 'checking')
  const [attempt, setAttempt] = useState(0)
  const checkedUser = useRef<string | null>(null)

  useEffect(() => {
    if (mockMode || !userId) {
      checkedUser.current = userId
      setPhase('ready')
      return
    }

    if (app.ownedListings.length) {
      checkedUser.current = userId
      setPhase('ready')
      return
    }

    if (checkedUser.current === userId && (phase === 'checking' || phase === 'syncing' || phase === 'ready' || phase === 'error')) return

    const controller = new AbortController()
    checkedUser.current = userId
    setPhase('checking')
    void getOwnedListings(controller.signal).then((items) => {
      if (controller.signal.aborted) return
      if (!items.length) {
        // An authoritative empty response is safe to render as the normal
        // empty state; unlike the provider's initial [] this is not a loading
        // sentinel.
        setPhase('ready')
        return
      }
      setPhase('syncing')
      window.dispatchEvent(new Event('catalog:updated'))
    }).catch(() => {
      if (!controller.signal.aborted) setPhase('error')
    })
    return () => controller.abort()
  }, [app.ownedListings.length, attempt, phase, userId])

  useEffect(() => {
    if (phase === 'syncing' && app.ownedListings.length) setPhase('ready')
  }, [app.ownedListings.length, phase])

  useEffect(() => {
    if (phase !== 'syncing') return
    const timeout = window.setTimeout(() => setPhase('error'), PROVIDER_SYNC_TIMEOUT_MS)
    return () => window.clearTimeout(timeout)
  }, [phase])

  if (mockMode) return children

  const checkingNewUser = Boolean(userId && checkedUser.current !== userId && !app.ownedListings.length)
  if ((phase === 'checking' || phase === 'syncing' || checkingNewUser) && !app.ownedListings.length) {
    return <div className="route-loading customer-owned-listings-loading" role="status" aria-live="polite"><span /><strong>{text.loading}</strong><p>{text.help}</p></div>
  }
  if (phase === 'error' && !app.ownedListings.length) {
    return <div className="route-error customer-owned-listings-error" role="alert"><h1>{text.error}</h1><p>{text.errorHelp}</p><button type="button" onClick={() => { checkedUser.current = null; setPhase('checking'); setAttempt((value) => value + 1) }}>{text.retry}</button></div>
  }
  return children
}
