import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '@/api/client'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'
import './saved-ai-searches.css'

type Summary = { id: string; matcher: 'ai.v1'; name: string; revision: number; enabled: boolean }
type Page = { items: Summary[]; next_cursor: string | null; collection_count: number }
const copy = {
  es: { title: 'Búsquedas IA guardadas', unnamed: 'Búsqueda sin nombre', remove: 'Eliminar', more: 'Cargar más', retry: 'Reintentar', error: 'No se pudieron cargar o actualizar las búsquedas guardadas.', count: 'Guardadas en total', loading: 'Cargando…' },
  en: { title: 'Saved AI searches', unnamed: 'Unnamed search', remove: 'Delete', more: 'Load more', retry: 'Retry', error: 'Saved searches could not be loaded or updated.', count: 'Total saved', loading: 'Loading…' },
  ru: { title: 'Сохранённые AI-поиски', unnamed: 'Поиск без названия', remove: 'Удалить', more: 'Загрузить ещё', retry: 'Повторить', error: 'Не удалось загрузить или изменить сохранённые поиски.', count: 'Всего сохранено', loading: 'Загрузка…' },
}

export function SavedAISearches({ empty }: { empty?: ReactNode }) {
  const { currentUser } = useApp()
  return currentUser && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(currentUser.id) ? <OwnedSavedAISearches key={currentUser.id} empty={empty} /> : <>{empty}</>
}

function OwnedSavedAISearches({ empty }: { empty?: ReactNode }) {
  const { language } = useI18n()
  const t = copy[language as keyof typeof copy] ?? copy.es
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState(false)
  const [busy, setBusy] = useState(false)
  const lifetime = useRef<AbortController | null>(null)
  const running = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    lifetime.current = controller
    void api<Page>('/saved-searches/ai', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setPage(value)
    }).catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [])

  async function update(id?: string, after?: string) {
    const controller = lifetime.current
    if (!controller || controller.signal.aborted || running.current) return
    running.current = true
    setBusy(true)
    setError(false)
    try {
      if (id) await api<void>(`/saved-searches/${id}`, { method: 'DELETE', signal: controller.signal })
      const value = await api<Page>(`/saved-searches/ai${after ? `?after=${encodeURIComponent(after)}` : ''}`, { signal: controller.signal })
      if (!controller.signal.aborted) setPage(previous => ({ ...value, items: after ? [...(previous?.items ?? []), ...value.items] : value.items }))
    } catch { if (!controller.signal.aborted) setError(true) }
    finally { running.current = false; if (!controller.signal.aborted) setBusy(false) }
  }

  if (!page?.items.length && !error) return <>{empty}</>
  return <section className="saved-ai-collection" aria-label={t.title} aria-busy={busy}>
    <h2>{t.title}</h2>
    {page ? <p>{t.count}: {page.collection_count}</p> : null}
    {error ? <p role="alert">{t.error} <Button disabled={busy} onClick={() => void update()}>{t.retry}</Button></p> : null}
    {page?.items.map(item => <article key={item.id} className="saved-ai-collection__item">
      <h3>{item.name || t.unnamed}</h3>
      <Button variant="outline" disabled={busy} aria-label={`${t.remove}: ${item.name || t.unnamed}`} onClick={() => void update(item.id)}>{t.remove}</Button>
    </article>)}
    {page?.next_cursor ? <Button disabled={busy} onClick={() => void update(undefined, page.next_cursor!)}>{busy ? t.loading : t.more}</Button> : null}
  </section>
}
