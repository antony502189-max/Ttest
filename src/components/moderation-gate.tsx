import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, Ban, Mail, ShieldAlert } from 'lucide-react'
import { useLocation } from 'react-router'
import { toast } from 'sonner'
import { getModerationNotices, getMyRestriction, markModerationNoticeRead, type MyRestriction } from '@/api/moderation'
import { Button } from '@/components/ui/button'
import { useApp } from '@/contexts/app-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const MODERATION_REFRESH_MS = 60_000

const labels = {
  full: 'Tu cuenta está restringida',
  publish: 'La publicación de anuncios está restringida',
  view_listings: 'El acceso a anuncios está restringido',
} as const

function formattedUntil(value: string | null) {
  if (!value) return 'Sin fecha final'
  return `Hasta ${new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date(value))}`
}

function RestrictionCard({ restriction, full = false }: { restriction: MyRestriction; full?: boolean }) {
  const Icon = full ? Ban : ShieldAlert
  return <section className={full ? 'restriction-screen' : 'restriction-banner'} role="alert">
    <div className="restriction-card">
      <Icon aria-hidden="true" />
      <div>
        <strong>{labels[restriction.restrictionType]}</strong>
        <p>{restriction.reason}</p>
        <span>{formattedUntil(restriction.until)}</span>
        <a href={`mailto:${restriction.supportEmail}`}><Mail aria-hidden="true" /> Contactar con soporte: {restriction.supportEmail}</a>
      </div>
    </div>
  </section>
}

function ProductionModerationGate({ children }: { children: ReactNode }) {
  const { currentUser, logout } = useApp()
  const location = useLocation()
  const [restriction, setRestriction] = useState<MyRestriction | null>(null)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)

  useEffect(() => {
    if (!currentUser) {
      setRestriction(null)
      setLoadedFor(null)
      return
    }
    let cancelled = false
    void Promise.all([getMyRestriction(), getModerationNotices()]).then(([active, notices]) => {
      if (cancelled) return
      setRestriction(active)
      setLoadedFor(currentUser.id)
      const unread = notices.filter((notice) => !notice.readAt)
      for (const notice of unread.slice(0, 3)) {
        toast.info(notice.title, { description: notice.body, duration: 8_000 })
        void markModerationNoticeRead(notice.id).catch(() => undefined)
      }
    }).catch(() => {
      if (!cancelled) setLoadedFor(currentUser.id)
    })
    return () => { cancelled = true }
  }, [currentUser?.id, location.pathname])

  useEffect(() => {
    if (!currentUser) return
    let cancelled = false
    const refresh = () => {
      void getMyRestriction().then((active) => {
        if (!cancelled) setRestriction(active)
      }).catch(() => undefined)
    }
    const interval = window.setInterval(refresh, MODERATION_REFRESH_MS)
    window.addEventListener('focus', refresh)
    return () => {
      cancelled = true
      window.clearInterval(interval)
      window.removeEventListener('focus', refresh)
    }
  }, [currentUser?.id])

  useEffect(() => {
    if (!currentUser || !restriction?.until) return
    const remaining = new Date(restriction.until).getTime() - Date.now()
    if (remaining > MODERATION_REFRESH_MS) return
    const timer = window.setTimeout(() => {
      void getMyRestriction().then(setRestriction).catch(() => undefined)
    }, Math.max(1_000, remaining + 1_000))
    return () => window.clearTimeout(timer)
  }, [currentUser?.id, restriction])

  const routeBlocked = useMemo(() => {
    if (!restriction) return false
    if (restriction.restrictionType === 'full') return true
    if (restriction.restrictionType === 'publish') {
      return location.pathname === '/publicar' || /^\/mis-anuncios\/[^/]+\/editar$/.test(location.pathname)
    }
    if (restriction.restrictionType === 'view_listings') {
      return location.pathname === '/buscar'
        || location.pathname === '/favoritos'
        || location.pathname.startsWith('/habitacion/')
    }
    return false
  }, [location.pathname, restriction])

  if (currentUser && loadedFor !== currentUser.id) {
    return <div className="route-loading" role="status" aria-live="polite"><span /><strong>Comprobando acceso…</strong></div>
  }

  if (restriction?.restrictionType === 'full') {
    return <main className="restriction-screen restriction-screen--full">
      <RestrictionCard restriction={restriction} full />
      <Button variant="outline" onClick={logout}>Cerrar sesión</Button>
    </main>
  }

  if (restriction && routeBlocked) {
    return <main className="restriction-screen">
      <RestrictionCard restriction={restriction} full />
      <button type="button" className="restriction-back" onClick={() => history.back()}>Volver</button>
    </main>
  }

  return <>
    {restriction ? <RestrictionCard restriction={restriction} /> : null}
    {children}
  </>
}

export function ModerationGate({ children }: { children: ReactNode }) {
  if (mockMode) return <>{children}</>
  return <ProductionModerationGate>{children}</ProductionModerationGate>
}

export function RestrictedActionHint() {
  return <span className="restriction-action-hint"><AlertTriangle aria-hidden="true" /> Acción restringida por administración</span>
}
