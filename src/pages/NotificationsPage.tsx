import { useCallback, useEffect, useState } from 'react'
import { Bell, CheckCheck } from 'lucide-react'
import { Link } from 'react-router'
import { getNotifications, markAllNotificationsRead, markNotificationRead, type NotificationItem } from '@/api/notifications'
import { Button } from '@/components/ui/button'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

function formattedDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    if (mockMode) {
      setItems([])
      setUnread(0)
      setLoading(false)
      return
    }
    try {
      const page = await getNotifications()
      setItems(page.items)
      setUnread(page.unreadCount)
    } catch {
      setError(true)
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  const read = async (item: NotificationItem) => {
    if (item.readAt) return
    try {
      await markNotificationRead(item.id)
      setItems((current) => current.map((candidate) => candidate.id === item.id ? { ...candidate, readAt: new Date().toISOString() } : candidate))
      setUnread((current) => Math.max(0, current - 1))
    } catch { setError(true) }
  }
  const readAll = async () => {
    try {
      await markAllNotificationsRead()
      setItems((current) => current.map((item) => item.readAt ? item : { ...item, readAt: new Date().toISOString() }))
      setUnread(0)
    } catch { setError(true) }
  }
  return <section className="section notifications-page" aria-labelledby="notifications-title">
    <div className="container">
      <div className="section-heading"><div><p className="eyebrow">Cuenta</p><h1 id="notifications-title">Notificaciones</h1><p>Actividad de tus anuncios, favoritos y búsquedas guardadas.</p></div>{unread ? <Button variant="outline" onClick={() => void readAll()}><CheckCheck data-icon="inline-start" />Marcar todas como leídas</Button> : null}</div>
      {error ? <div className="account-empty" role="alert"><Bell /><h2>No pudimos cargar las notificaciones</h2><Button onClick={() => void load()}>Reintentar</Button></div> : null}
      {loading ? <p role="status">Cargando notificaciones…</p> : null}
      {!loading && !error && !items.length ? <div className="account-empty"><Bell /><h2>Aún no tienes notificaciones</h2><p>Te avisaremos cuando haya actividad relevante.</p></div> : null}
      {!loading && !error && items.length ? <ol className="notifications-list">{items.map((item) => <li key={item.id} className={item.readAt ? undefined : 'is-unread'}><article><div><h2>{item.title}</h2><p>{item.body}</p><time dateTime={item.createdAt}>{formattedDate(item.createdAt)}</time></div><div className="notifications-list__actions">{item.entityListingId ? <Button asChild variant="outline" size="sm"><Link to={`/habitacion/${item.entityListingId}`} onClick={() => void read(item)}>Ver anuncio</Link></Button> : null}{!item.readAt ? <Button variant="ghost" size="sm" onClick={() => void read(item)}>Marcar leída</Button> : null}</div></article></li>)}</ol> : null}
    </div>
  </section>
}
