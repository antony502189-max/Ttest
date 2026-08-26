import { useCallback, useEffect, useState } from 'react'
import { Bell, CheckCheck } from 'lucide-react'
import { Link } from 'react-router'
import { getNotifications, markAllNotificationsRead, markNotificationRead, type NotificationItem } from '@/api/notifications'
import { Button } from '@/components/ui/button'
import { useI18n, type Language } from '@/contexts/i18n-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

const pageCopy: Record<Language, {
  account: string
  title: string
  description: string
  markAll: string
  loadError: string
  retry: string
  loading: string
  emptyTitle: string
  emptyBody: string
  openListing: string
  openFavorites: string
  openMyListings: string
  markRead: string
}> = {
  es: {
    account: 'Cuenta',
    title: 'Notificaciones',
    description: 'Actividad de tus anuncios, favoritos y búsquedas guardadas.',
    markAll: 'Marcar todas como leídas',
    loadError: 'No pudimos cargar las notificaciones',
    retry: 'Reintentar',
    loading: 'Cargando notificaciones…',
    emptyTitle: 'Aún no tienes notificaciones',
    emptyBody: 'Te avisaremos cuando haya actividad relevante.',
    openListing: 'Ver anuncio',
    openFavorites: 'Ver favoritos',
    openMyListings: 'Ir a Mis anuncios',
    markRead: 'Marcar leída',
  },
  en: {
    account: 'Account',
    title: 'Notifications',
    description: 'Activity from your listings, favorites and saved searches.',
    markAll: 'Mark all as read',
    loadError: 'We could not load notifications',
    retry: 'Try again',
    loading: 'Loading notifications…',
    emptyTitle: 'You have no notifications yet',
    emptyBody: 'We will notify you when something relevant happens.',
    openListing: 'View listing',
    openFavorites: 'View favorites',
    openMyListings: 'Go to My listings',
    markRead: 'Mark as read',
  },
  ru: {
    account: 'Аккаунт',
    title: 'Уведомления',
    description: 'События ваших объявлений, избранного и сохранённых поисков.',
    markAll: 'Отметить все как прочитанные',
    loadError: 'Не удалось загрузить уведомления',
    retry: 'Повторить',
    loading: 'Загрузка уведомлений…',
    emptyTitle: 'У вас пока нет уведомлений',
    emptyBody: 'Мы сообщим, когда произойдёт важное событие.',
    openListing: 'Открыть объявление',
    openFavorites: 'Открыть избранное',
    openMyListings: 'Перейти к моим объявлениям',
    markRead: 'Отметить прочитанным',
  },
}

const productNotificationCopy: Record<string, Record<Language, { title: string; body: string }>> = {
  listing_submitted: {
    es: { title: 'Tu anuncio se ha enviado', body: 'Revisaremos tu anuncio antes de publicarlo.' },
    en: { title: 'Your listing was submitted', body: 'We will review your listing before publishing it.' },
    ru: { title: 'Объявление отправлено', body: 'Мы проверим объявление перед публикацией.' },
  },
  listing_published: {
    es: { title: 'Tu anuncio está publicado', body: 'Tu anuncio ya es visible en 112233.es.' },
    en: { title: 'Your listing is published', body: 'Your listing is now visible on 112233.es.' },
    ru: { title: 'Объявление опубликовано', body: 'Ваше объявление уже видно на 112233.es.' },
  },
  listing_republished: {
    es: { title: 'Tu anuncio se ha republicado', body: 'Tu anuncio vuelve a estar visible en 112233.es.' },
    en: { title: 'Your listing was republished', body: 'Your listing is visible on 112233.es again.' },
    ru: { title: 'Объявление опубликовано повторно', body: 'Ваше объявление снова видно на 112233.es.' },
  },
  listing_rejected: {
    es: { title: 'Tu anuncio necesita cambios', body: 'Revisa el estado del anuncio antes de volver a publicarlo.' },
    en: { title: 'Your listing needs changes', body: 'Review its status before submitting it again.' },
    ru: { title: 'Объявление требует изменений', body: 'Проверьте статус объявления перед повторной отправкой.' },
  },
  listing_hidden: {
    es: { title: 'Tu anuncio está oculto', body: 'Tu anuncio ya no aparece en las búsquedas públicas.' },
    en: { title: 'Your listing is hidden', body: 'Your listing no longer appears in public search.' },
    ru: { title: 'Объявление скрыто', body: 'Объявление больше не показывается в публичном поиске.' },
  },
  listing_closed: {
    es: { title: 'Tu anuncio está cerrado', body: 'Tu anuncio ya no aparece en las búsquedas públicas.' },
    en: { title: 'Your listing is closed', body: 'Your listing no longer appears in public search.' },
    ru: { title: 'Объявление закрыто', body: 'Объявление больше не показывается в публичном поиске.' },
  },
  listing_expired: {
    es: { title: 'Tu anuncio ha finalizado', body: 'El anuncio ha vencido. Puedes renovarlo desde Mis anuncios.' },
    en: { title: 'Your listing has expired', body: 'The listing expired. You can renew it from My listings.' },
    ru: { title: 'Срок объявления истёк', body: 'Объявление завершено. Его можно продлить в разделе «Мои объявления».' },
  },
  saved_search_match: {
    es: { title: 'Nueva habitación para tu búsqueda guardada', body: 'Ha aparecido una nueva habitación que coincide con tu búsqueda.' },
    en: { title: 'New room for your saved search', body: 'A new room matching your saved search is available.' },
    ru: { title: 'Новое совпадение для сохранённого поиска', body: 'Появилась новая комната, подходящая под ваш сохранённый поиск.' },
  },
  favorite_unavailable: {
    es: { title: 'Un favorito ya no está disponible', body: 'Uno de tus favoritos ya no aparece en las búsquedas públicas.' },
    en: { title: 'A favorite is no longer available', body: 'One of your favorites no longer appears in public search.' },
    ru: { title: 'Объявление из избранного недоступно', body: 'Одно из избранных объявлений больше не показывается в публичном поиске.' },
  },
  listing_restricted: {
    es: { title: 'Uno de tus anuncios se ha ocultado', body: 'Se ha aplicado una restricción de moderación al anuncio.' },
    en: { title: 'One of your listings was hidden', body: 'A moderation restriction was applied to the listing.' },
    ru: { title: 'Одно из объявлений скрыто', body: 'К объявлению применено ограничение модерации.' },
  },
  listing_unrestricted: {
    es: { title: 'La restricción de tu anuncio se ha retirado', body: 'El anuncio vuelve a regirse por su estado normal.' },
    en: { title: 'Your listing restriction was removed', body: 'The listing is available according to its normal status again.' },
    ru: { title: 'Ограничение объявления снято', body: 'Объявление снова работает в соответствии с обычным статусом.' },
  },
  listing_restriction_expired: {
    es: { title: 'La restricción de tu anuncio ha finalizado', body: 'La restricción administrativa del anuncio ha finalizado.' },
    en: { title: 'Your listing restriction has ended', body: 'The administrative restriction on the listing has ended.' },
    ru: { title: 'Ограничение объявления завершено', body: 'Административное ограничение объявления завершилось.' },
  },
  user_restriction_expired: {
    es: { title: 'Tu restricción ha finalizado', body: 'El acceso correspondiente se ha restaurado automáticamente.' },
    en: { title: 'Your restriction has ended', body: 'The corresponding access has been restored automatically.' },
    ru: { title: 'Ограничение аккаунта завершено', body: 'Соответствующий доступ восстановлен автоматически.' },
  },
}

const MY_LISTING_NOTIFICATION_TYPES = new Set([
  'listing_submitted',
  'listing_rejected',
  'listing_hidden',
  'listing_closed',
  'listing_expired',
  'listing_restricted',
  'listing_unrestricted',
  'listing_restriction_expired',
])

function formattedDate(value: string, language: Language) {
  const locale = language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES'
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function displayNotification(item: NotificationItem, language: Language) {
  return productNotificationCopy[item.type]?.[language] ?? { title: item.title, body: item.body }
}

function notificationTarget(item: NotificationItem, copy: typeof pageCopy.es) {
  if (item.type === 'favorite_unavailable') return { to: '/favoritos', label: copy.openFavorites }
  if (MY_LISTING_NOTIFICATION_TYPES.has(item.type)) return { to: '/mis-anuncios', label: copy.openMyListings }
  if (item.entityListingId) return { to: `/habitacion/${item.entityListingId}`, label: copy.openListing }
  return null
}

export function NotificationsPage() {
  const { language } = useI18n()
  const copy = pageCopy[language]
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      const page = await getNotifications()
      setItems(page.items)
      setUnread(page.unreadCount)
    } catch {
      if (mockMode) {
        setItems([])
        setUnread(0)
      } else {
        setError(true)
      }
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
      <div className="section-heading"><div><p className="eyebrow">{copy.account}</p><h1 id="notifications-title">{copy.title}</h1><p>{copy.description}</p></div>{unread ? <Button variant="outline" onClick={() => void readAll()}><CheckCheck data-icon="inline-start" />{copy.markAll}</Button> : null}</div>
      {error ? <div className="account-empty" role="alert"><Bell /><h2>{copy.loadError}</h2><Button onClick={() => void load()}>{copy.retry}</Button></div> : null}
      {loading ? <p role="status">{copy.loading}</p> : null}
      {!loading && !error && !items.length ? <div className="account-empty"><Bell /><h2>{copy.emptyTitle}</h2><p>{copy.emptyBody}</p></div> : null}
      {!loading && !error && items.length ? <ol className="notifications-list">{items.map((item) => {
        const display = displayNotification(item, language)
        const target = notificationTarget(item, copy)
        return <li key={item.id} className={item.readAt ? undefined : 'is-unread'}><article><div><h2>{display.title}</h2><p>{display.body}</p><time dateTime={item.createdAt}>{formattedDate(item.createdAt, language)}</time></div><div className="notifications-list__actions">{target ? <Button asChild variant="outline" size="sm"><Link to={target.to} onClick={() => void read(item)}>{target.label}</Link></Button> : null}{!item.readAt ? <Button variant="ghost" size="sm" onClick={() => void read(item)}>{copy.markRead}</Button> : null}</div></article></li>
      })}</ol> : null}
    </div>
  </section>
}
