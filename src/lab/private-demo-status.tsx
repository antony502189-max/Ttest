import { useEffect, useState } from 'react'

export const PRIVATE_DEMO = true
export function PrivateDemoStatus({ refreshKey, onBlocked }: { refreshKey: string; onBlocked: (blocked: boolean) => void }) {
  const [message, setMessage] = useState('Проверяем отдельный лимит демонстрации…')
  useEffect(() => {
    const controller = new AbortController()
    onBlocked(true)
    void fetch('/api/v1/private-demo/status', { cache: 'no-store', credentials: 'omit', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('Private demo unavailable')
        const status = await response.json() as { attempts: number; maximum: number; exhausted: boolean; halted: boolean }
        if (!Number.isInteger(status.attempts) || status.maximum !== 3 || status.attempts < 0 || status.attempts > 3
          || typeof status.exhausted !== 'boolean' || typeof status.halted !== 'boolean') throw new Error('Invalid private status')
        if (controller.signal.aborted) return
        const blocked = status.exhausted || status.halted || status.attempts === 3
        onBlocked(blocked)
        setMessage(status.halted ? 'Демонстрация остановлена после неопределённого исхода. Повторный платный запуск закрыт.'
          : blocked ? 'Демо-лимит исчерпан: доступны только сохранённые результаты.'
            : `Отдельный лимит модели: ${status.attempts}/3. Шаги выполняются один раз в одной сессии.`)
      }).catch(() => {
        if (!controller.signal.aborted) {
          onBlocked(true)
          setMessage('Демостенд недоступен. Новые обращения закрыты; сохранённые результаты не изменены.')
        }
      })
    return () => controller.abort()
  }, [refreshKey, onBlocked])
  return <p role="status" data-private-demo-status data-i18n-exempt>{message}</p>
}
