import { useEffect, useState } from 'react'
import { useI18n } from '@/contexts/i18n-context'

export const PRIVATE_DEMO = true
export function PrivateDemoStatus({ refreshKey, onBlocked, onReason }: { refreshKey: string; onBlocked: (blocked: boolean) => void; onReason?: (reason: string) => void }) {
  const { t } = useI18n()
  const [message, setMessage] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    onBlocked(true)
    setMessage(t('Comprobando la búsqueda…'))
    onReason?.(t('Comprobando la búsqueda…'))
    void fetch('/ai-pilot/api/v1/private-demo/status', { cache: 'no-store', credentials: 'include', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Unavailable')
        const status = await response.json() as { attempts: number; maximum: number; exhausted: boolean; halted: boolean; approved: boolean; catalog_ready: boolean; local_housing_available?: boolean }
        if (!Number.isSafeInteger(status.attempts) || !Number.isSafeInteger(status.maximum) || status.maximum < 1 || status.attempts < 0
          || (status.local_housing_available !== undefined && typeof status.local_housing_available !== 'boolean')
          || typeof status.exhausted !== 'boolean' || typeof status.halted !== 'boolean' || typeof status.approved !== 'boolean' || typeof status.catalog_ready !== 'boolean') throw new Error('Invalid status')
        if (controller.signal.aborted) return
        const localAvailable = status.local_housing_available === true
        const blocked = !status.catalog_ready || (!localAvailable && (status.exhausted || status.halted || !status.approved))
        onBlocked(blocked)
        const reason = !status.catalog_ready ? t('Los anuncios se están actualizando. Inténtalo de nuevo en unos minutos.')
          : blocked ? t('Las nuevas búsquedas no están disponibles temporalmente. Puedes abrir los resultados guardados.')
            : t('Busca por voz o texto: tipo de vivienda, presupuesto y comodidades.')
        setMessage(reason)
        onReason?.(blocked ? reason : '')
      }).catch(() => { if (!controller.signal.aborted) { onBlocked(true); setMessage(t('La búsqueda no está disponible temporalmente.')); onReason?.(t('La búsqueda no está disponible temporalmente.')) } })
    return () => controller.abort()
  }, [refreshKey, onBlocked, onReason, t])
  return <p role="status" data-private-demo-status>{message}</p>
}
