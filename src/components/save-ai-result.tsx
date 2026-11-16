import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'

const copy = {
  es: { save: 'Guardar búsqueda y activar avisos', register: 'Regístrate para guardar esta búsqueda', hint: 'Después de acceder, vuelve a esta búsqueda y pulsa Guardar. Recibirás avisos dentro de tu cuenta cuando haya nuevas coincidencias verificadas.', saved: 'Búsqueda guardada. Puedes pausar los avisos en Búsquedas guardadas.', busy: 'Guardando…', error: 'No se pudo guardar. Comprueba tu acceso y vuelve a intentarlo; no se gastará otra búsqueda.', manage: 'Ver búsquedas guardadas' },
  en: { save: 'Save search and enable alerts', register: 'Register to save this search', hint: 'After signing in, return to this search and press Save. You will receive alerts in your account when new verified matches appear.', saved: 'Search saved. You can pause alerts in Saved searches.', busy: 'Saving…', error: 'Could not save. Check your login and try again; this will not spend another search.', manage: 'View saved searches' },
  ru: { save: 'Сохранить поиск и включить уведомления', register: 'Зарегистрироваться, чтобы сохранить поиск', hint: 'После входа вернитесь к этому поиску и нажмите «Сохранить». Уведомления появятся в аккаунте, когда будут новые проверенные совпадения.', saved: 'Поиск сохранён. Уведомления можно приостановить в сохранённых поисках.', busy: 'Сохраняем…', error: 'Не удалось сохранить. Проверьте вход и повторите попытку — новая попытка AI-поиска не спишется.', manage: 'Открыть сохранённые поиски' },
}

export function SaveAIResult({ resultRef, available, disabled }: { resultRef: string; available: boolean; disabled: boolean }) {
  const { currentUser } = useApp()
  const { language } = useI18n()
  const t = copy[language as keyof typeof copy] ?? copy.es
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(false)
  const running = useRef(false)
  const lifetime = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    lifetime.current = controller
    if (available) void api<{ save: boolean }>('/saved-searches/ai/capabilities', { signal: controller.signal, cache: 'no-store' })
      .then(value => { if (!controller.signal.aborted) setReady(value.save === true) }).catch(() => {})
    return () => controller.abort()
  }, [available])

  async function save() {
    const controller = lifetime.current
    if (!currentUser || !controller || controller.signal.aborted || running.current || disabled) return
    running.current = true; setBusy(true); setError(false)
    try {
      // Token and typed criteria stay in memory, never local/session storage.
      // The public guest request omits bearer; only the primary save uses it.
      const issued = await api<{ token: string }>(`/ai-search/results/${encodeURIComponent(resultRef)}/save-token`, {
        method: 'POST', headers: { 'X-AI-Request': '1' }, signal: controller.signal, cache: 'no-store',
      })
      await api('/saved-searches/ai', { method: 'POST', body: JSON.stringify({ token: issued.token }), signal: controller.signal, cache: 'no-store' })
      if (!controller.signal.aborted) setSaved(true)
    } catch { if (!controller.signal.aborted) setError(true) }
    finally { running.current = false; if (!controller.signal.aborted) setBusy(false) }
  }

  if (!available || !ready) return null
  return <div data-i18n-exempt>
    {saved ? <p role="status">{t.saved} <Link to="/busquedas-guardadas">{t.manage}</Link></p> : currentUser
      ? <Button type="button" variant="outline" disabled={disabled || busy} onClick={() => void save()}>{busy ? t.busy : t.save}</Button>
      : <><Link to="/registro" state={{ returnTo: "/?ai=save" }}>{t.register}</Link><p>{t.hint}</p></>}
    {error ? <p role="alert">{t.error}</p> : null}
  </div>
}
