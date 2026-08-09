import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { AlertTriangle, Ban, Mail, ShieldAlert } from 'lucide-react'
import { useLocation } from 'react-router'
import { toast } from 'sonner'
import { getModerationNotices, getMyRestriction, markModerationNoticeRead, type MyRestriction } from '@/api/moderation'
import { Button } from '@/components/ui/button'
import { useApp } from '@/contexts/app-context'

const labels = {
  full: 'Tu cuenta está restringida',
  publish: 'La publicación de anuncios está restringida',
  view_listings: 'El acceso a anuncios está restringido',
} as const

function formattedUntil(value: string) {
  return new Intl.DateTimeFormat('es-ES', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date(value))
}

function RestrictionCard({ restriction, full = false }: { restriction: MyRestriction; full?: boolean }) {
  const Icon = full ? Ban : ShieldAlert
  return <section className={full ? 'restriction-screen' : 'restriction-banner'} role="alert">
    <div className="restriction-card">
      <Icon aria-hidden="true" />
      <div>
        <strong>{labels[restriction.restrictionType]}</strong>
        <p>{restriction.reason}</p>
        <span>Hasta {formattedUntil(restriction.until)}</span>
        <a href={`mailto:${restriction.supportEmail}`}><Mail aria-hidden="true" /> Contactar con soporte: {restriction.supportEmail}</a>
      </div>
    </div>
  </section>
}

export function ModerationGate({ children }: { children: ReactNode }) {
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
  }, [currentUser?.id])

  const routeBlocked = useMemo(() => {
    if (!restriction) return false
    if (restriction.restrictionType === 'full') return true
    if (restriction.restrictionType === 'publish') {
      return location.pathname === '/publicar' || /^\/mis-anuncios\/[^/]+\/editar$/.test(location.pathname)
    }
    return restriction.restrictionType === 'view_listings' && location.pathname.startsWith('/habitacion/')
  }, [location.pathname, restriction])

  if (currentUser && loadedFor !== currentUser.id) return <>{children}</>

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

export function RestrictedActionHint() {
  return <span className="restriction-action-hint"><AlertTriangle aria-hidden="true" /> Acción restringida por administración</span>
}
