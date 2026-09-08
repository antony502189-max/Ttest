import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { getOwnedListings } from '@/api/listings'
import { AppContext, useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import type { Listing } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

type Phase = 'checking' | 'ready' | 'error'
type Snapshot = { userId: string; items: Listing[] }

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
 * with an empty array while the request is in flight, so rendering the normal
 * empty state at that point makes real listings appear to have been deleted.
 * This gate distinguishes "not loaded yet" from an authoritative empty list
 * and keeps a same-user server snapshot visible across refresh races.
 */
export function OwnedListingsHydrationGate({ children }: { children: ReactNode }) {
  const app = useApp()
  const { language } = useI18n()
  const text = copy[language]
  const userId = app.currentUser?.id ?? null
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [phase, setPhase] = useState<Phase>(() => mockMode || app.ownedListings.length ? 'ready' : 'checking')
  const [attempt, setAttempt] = useState(0)
  const checkedUser = useRef<string | null>(null)

  const sameUserSnapshot = snapshot?.userId === userId ? snapshot.items : null

  useEffect(() => {
    if (mockMode || !userId) {
      checkedUser.current = userId
      setSnapshot(null)
      setPhase('ready')
      return
    }

    if (app.ownedListings.length) {
      checkedUser.current = userId
      setSnapshot(null)
      setPhase('ready')
      return
    }

    if (checkedUser.current === userId && (phase === 'ready' || phase === 'error')) return

    const controller = new AbortController()
    checkedUser.current = userId
    setPhase('checking')
    void getOwnedListings(controller.signal).then((items) => {
      if (controller.signal.aborted) return
      setSnapshot({ userId, items })
      setPhase('ready')
      if (items.length) window.dispatchEvent(new Event('catalog:updated'))
    }).catch(() => {
      if (!controller.signal.aborted) setPhase('error')
    })
    return () => controller.abort()
  }, [app.ownedListings, attempt, phase, userId])

  const effectiveValue = useMemo(() => {
    if (app.ownedListings.length || sameUserSnapshot === null) return app
    return { ...app, ownedListings: sameUserSnapshot }
  }, [app, sameUserSnapshot])

  if (mockMode) return children
  if (phase === 'checking' && !sameUserSnapshot?.length) {
    return <div className="route-loading customer-owned-listings-loading" role="status" aria-live="polite"><span /><strong>{text.loading}</strong><p>{text.help}</p></div>
  }
  if (phase === 'error' && !sameUserSnapshot?.length) {
    return <div className="route-error customer-owned-listings-error" role="alert"><h1>{text.error}</h1><p>{text.errorHelp}</p><button type="button" onClick={() => { checkedUser.current = null; setAttempt((value) => value + 1) }}>{text.retry}</button></div>
  }
  return <AppContext.Provider value={effectiveValue}>{children}</AppContext.Provider>
}
