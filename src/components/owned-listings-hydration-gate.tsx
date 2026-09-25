import type { ReactNode } from 'react'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import '@/owned-listings-hydration.css'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

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
 * The provider owns the single authoritative /listings/mine request.
 * This gate only reflects that hydration state, so route entry never launches
 * a duplicate owner-list request and never mistakes an in-flight [] for a
 * confirmed empty account.
 */
export function OwnedListingsHydrationGate({ children }: { children: ReactNode }) {
  const app = useApp()
  const { language } = useI18n()
  const text = copy[language]

  if (mockMode) return children

  if (app.ownedListingsHydrationStatus !== 'ready' && app.ownedListings.length === 0) {
    if (app.ownedListingsHydrationStatus === 'error') {
      return <div className="customer-owned-listings-error" role="alert">
        <strong>{text.error}</strong>
        <p>{text.errorHelp}</p>
        <button type="button" onClick={() => { void app.refreshOwnedListings() }}>{text.retry}</button>
      </div>
    }
    return <div className="customer-owned-listings-loading" role="status" aria-live="polite">
      <span />
      <strong>{text.loading}</strong>
      <p>{text.help}</p>
    </div>
  }

  return children
}
