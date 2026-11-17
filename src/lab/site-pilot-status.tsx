import { useEffect, useState } from 'react'
import { useI18n } from '@/contexts/i18n-context'

export const PRIVATE_DEMO = true
export function PrivateDemoStatus({ refreshKey, onBlocked, onReason }: { refreshKey: string; onBlocked: (blocked: boolean) => void; onReason?: (reason: string) => void }) {
  const { t } = useI18n()
  const [message, setMessage] = useState('')
  useEffect(() => {
    let disposed = false, inFlight = false
    let retry: number | undefined
    let active: AbortController | null = null
    onBlocked(true)
    setMessage(t('Comprobando la búsqueda…'))
    onReason?.(t('Comprobando la búsqueda…'))
    async function check() {
      if (disposed || inFlight) return
      window.clearTimeout(retry)
      inFlight = true
      const controller = new AbortController()
      active = controller
      const timeout = window.setTimeout(() => controller.abort(), 8000)
      let blocked = true
      try {
        const response = await fetch('/ai-pilot/api/v1/private-demo/status', { cache: 'no-store', credentials: 'include', signal: controller.signal })
        if (!response.ok) throw new Error('Unavailable')
        const status = await response.json() as { attempts: number; maximum: number; exhausted: boolean; halted: boolean; approved: boolean; catalog_ready: boolean; local_housing_available?: boolean }
        if (!Number.isSafeInteger(status.attempts) || !Number.isSafeInteger(status.maximum) || status.maximum < 1 || status.attempts < 0
          || (status.local_housing_available !== undefined && typeof status.local_housing_available !== 'boolean')
          || typeof status.exhausted !== 'boolean' || typeof status.halted !== 'boolean' || typeof status.approved !== 'boolean' || typeof status.catalog_ready !== 'boolean') throw new Error('Invalid status')
        if (disposed) return
        const localAvailable = status.local_housing_available === true
        blocked = !status.catalog_ready || (!localAvailable && (status.exhausted || status.halted || !status.approved))
        onBlocked(blocked)
        const reason = !status.catalog_ready ? t('Estamos actualizando los anuncios. La búsqueda se reactivará automáticamente cuando estén listos.')
          : blocked ? t('Las nuevas búsquedas no están disponibles temporalmente. Puedes abrir los resultados guardados.')
            : t('Busca por voz o texto: tipo de vivienda, presupuesto y comodidades.')
        setMessage(reason)
        onReason?.(blocked ? reason : '')
      } catch {
        if (!disposed) { onBlocked(true); setMessage(t('La búsqueda no está disponible temporalmente.')); onReason?.(t('La búsqueda no está disponible temporalmente.')) }
      } finally {
        window.clearTimeout(timeout)
        inFlight = false
        active = null
        // Read-only availability probe only. Never retry a search or change its
        // idempotency key, payload, continuation, guest identity or quota here.
        if (!disposed && blocked) retry = window.setTimeout(() => void check(), 5000)
      }
    }
    const recheck = () => { if (document.visibilityState === 'visible') void check() }
    void check()
    window.addEventListener('focus', recheck)
    document.addEventListener('visibilitychange', recheck)
    return () => {
      disposed = true
      window.clearTimeout(retry)
      active?.abort()
      window.removeEventListener('focus', recheck)
      document.removeEventListener('visibilitychange', recheck)
    }
  }, [refreshKey, onBlocked, onReason, t])
  return <p role="status" data-private-demo-status>{message}</p>
}
