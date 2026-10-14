import { useEffect, useState } from 'react'
import { Bell } from 'lucide-react'
import { Link } from 'react-router'
import { getAdvertisingAvailability, getAdvertisingWaitlistStatus, subscribeAdvertisingVacancy, unsubscribeAdvertisingVacancy } from '@/api/commercial-advertisements'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'

export function AdvertisingVacancy({ onAvailable }: { onAvailable?: () => void } = {}) {
  const { currentUser } = useApp()
  const { t, language } = useI18n()
  const [busy, setBusy] = useState(false)
  const [subscribed, setSubscribed] = useState(false)
  const [available, setAvailable] = useState(false)
  const [error, setError] = useState('')
  const [channel, setChannel] = useState<'push' | 'site'>('site')
  const [pushEnabled, setPushEnabled] = useState<boolean | null>(null)
  useEffect(() => {
    let active = true
    setSubscribed(false)
    if (currentUser) void getAdvertisingWaitlistStatus().then((status) => {
      if (active) { setSubscribed(status.subscribed); setChannel(status.channel) }
    }).catch(() => { if (active) setError('No se pudo comprobar el aviso guardado. Inténtalo de nuevo.') })
    void getAdvertisingAvailability().then((status) => { if (active) setPushEnabled(status.pushEnabled) })
      .catch(() => { if (active) setPushEnabled(false) })
    return () => { active = false }
  }, [currentUser?.id])
  const subscribe = async () => {
    setBusy(true); setError('')
    try {
      // Request permission in the click handler before awaiting network I/O.
      const permissionRequest = pushEnabled && window.isSecureContext && 'Notification' in window
        && 'serviceWorker' in navigator && 'PushManager' in window
        ? Notification.requestPermission().catch(() => 'denied') : Promise.resolve('denied')
      const status = await getAdvertisingAvailability()
      if (status.available > 0) { setAvailable(true); return }
      let subscription: PushSubscriptionJSON | null = null
      if (status.pushEnabled && status.pushPublicKey && window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window) {
        const permission = await permissionRequest
        if (permission === 'granted') {
          const registration = await navigator.serviceWorker.register(`${import.meta.env.BASE_URL}advertising-sw.js`)
          await navigator.serviceWorker.ready
          const key = Uint8Array.from(atob(status.pushPublicKey.replace(/-/g, '+').replace(/_/g, '/')), (char) => char.charCodeAt(0))
          const push = await registration.pushManager.getSubscription() ?? await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
          subscription = push.toJSON()
        }
      }
      const result = await subscribeAdvertisingVacancy(language, subscription)
      setAvailable(result.available); setSubscribed(result.subscribed); setChannel(subscription ? 'push' : 'site')
    } catch { setError('No se pudo activar el aviso. Inténtalo de nuevo.') }
    finally { setBusy(false) }
  }
  const cancel = async () => {
    setBusy(true); setError('')
    try { await unsubscribeAdvertisingVacancy(); setSubscribed(false) }
    catch { setError('No se pudo cancelar el aviso. Inténtalo de nuevo.') }
    finally { setBusy(false) }
  }
  return <div className="advertising-vacancy">
    <p role="status">{t(available ? 'Ya hay un espacio disponible.' : 'No hay espacios publicitarios disponibles en este momento.')}</p>
    {available ? <Link className="commercial-ad__cta" to="/publicidad/nueva" onClick={onAvailable}>{t('Crear publicidad')}</Link>
      : !currentUser ? <Link className="commercial-ad__cta" to="/acceso" state={{ returnTo: '/publicidad/nueva' }}>{t('Inicia sesión para recibir un aviso')}</Link>
      : subscribed ? <><p role="status">{t(channel === 'push' ? 'Te enviaremos una notificación push cuando se libere un espacio.' : 'Te avisaremos en las notificaciones del sitio cuando se libere un espacio.')}</p><button type="button" disabled={busy} className="ad-flow__secondary" onClick={() => void cancel()}>{t('Cancelar aviso')}</button></>
      : <><p>{t('Recibe un aviso cuando se libere un espacio. Si permites las notificaciones del navegador, también recibirás un push.')}</p><button type="button" disabled={busy || pushEnabled === null} className="commercial-ad__cta" onClick={() => void subscribe()}><Bell aria-hidden="true" />{t('Avisarme cuando haya un espacio')}</button></>}
    {error ? <p role="alert">{t(error)}</p> : null}
  </div>
}
