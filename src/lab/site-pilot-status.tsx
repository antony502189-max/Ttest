import { useEffect, useState } from 'react'

export const PRIVATE_DEMO = true
export function PrivateDemoStatus({ refreshKey, onBlocked }: { refreshKey: string; onBlocked: (blocked: boolean) => void }) {
  const [message, setMessage] = useState('Проверяем доступ к модели…')
  useEffect(() => {
    const controller = new AbortController()
    onBlocked(true)
    void fetch('/ai-pilot/api/v1/private-demo/status', { cache: 'no-store', credentials: 'include', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Unavailable')
        const status = await response.json() as { attempts: number; maximum: number; exhausted: boolean; halted: boolean; approved: boolean; catalog_ready: boolean }
        if (!Number.isInteger(status.attempts) || status.maximum !== 50 || status.attempts < 0 || status.attempts > 50
          || typeof status.exhausted !== 'boolean' || typeof status.halted !== 'boolean' || typeof status.approved !== 'boolean' || typeof status.catalog_ready !== 'boolean') throw new Error('Invalid status')
        if (controller.signal.aborted) return
        onBlocked(status.exhausted || status.halted || !status.approved || !status.catalog_ready)
        setMessage(!status.catalog_ready ? 'Каталог устарел или недоступен. Новые обращения к модели остановлены до проверки данных.'
          : !status.approved ? 'Страница подготовлена. Обращения к модели ждут согласования тестового лимита.'
          : status.exhausted || status.halted ? 'Новые обращения остановлены. Доступны результаты завершённых поисков.'
            : `Общий лимит пилота: ${status.attempts}/50 обращений. Только условия аренды без личных данных.`)
      }).catch(() => { if (!controller.signal.aborted) { onBlocked(true); setMessage('Модель временно недоступна.') } })
    return () => controller.abort()
  }, [refreshKey, onBlocked])
  return <p role="status" data-private-demo-status data-i18n-exempt>{message}</p>
}
