import { useEffect, useRef, useState } from 'react'
import { AudioLines, Search } from 'lucide-react'
import { ApiError } from '@/api/client'
import { aiCapabilities, aiCardPage, aiResultPage, createAISession, getAIQuota, getAIResult, getAISession, sendAIMessage, type AIBudgetPrice, type AIMessage, type AISession } from '@/api/ai-search'
import { aiConditionRows, aiModeLabel, type AICommittedIntent } from '@/api/ai-intent'
import type { RentalMode } from '@/types'
import { hydrateIncompleteInternalGallery, type ListingCardPage } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { PropertyCard } from '@/components/marketplace'
import { AIResultMap } from '@/components/ai-result-map'
import { AIConditions } from '@/components/ai-conditions'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import '@/home-ai-search.css'

// Keying by identity discards private in-memory conversation on login/logout.
export function HomeAISearch({ homeMode }: { homeMode: RentalMode }) {
  const { currentUser } = useApp()
  return <AISearchPanel key={currentUser?.id ?? 'guest'} homeMode={homeMode} />
}

function AISearchPanel({ homeMode }: { homeMode: RentalMode }) {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [mapEnabled, setMapEnabled] = useState(false)
  const [mapVisible, setMapVisible] = useState(false)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [session, setSession] = useState<AISession | null>(null)
  const [modeChoice, setModeChoice] = useState<'' | 'keep' | 'none' | RentalMode>('')
  const [needsConversation, setNeedsConversation] = useState(false)
  const [pending, setPending] = useState<AIMessage | null>(null)
  const [result, setResult] = useState<{ ref: string; hash: string; committed: AICommittedIntent; prices: AIBudgetPrice[]; page: ListingCardPage } | null>(null)
  const [remaining, setRemaining] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const flight = useRef<AbortController | null>(null)
  const lock = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    void aiCapabilities(controller.signal).then(value => {
      if (!controller.signal.aborted) { setEnabled(value.text === true); setMapEnabled(value.map === true) }
    }).catch(() => { /* Ordinary search stays available when capability lookup fails. */ })
    return () => { controller.abort(); flight.current?.abort() }
  }, [])

  const ownedSessionId = session?.intent.session_id
  useEffect(() => {
    if (!open || !ownedSessionId || busy) return
    const controller = new AbortController()
    void getAIQuota(controller.signal).then(quota => {
      if (!controller.signal.aborted) setRemaining(quota.remaining)
    }).catch(() => { /* Keep the last authoritative counter if refresh fails. */ })
    return () => controller.abort()
  }, [open, ownedSessionId, busy])

  // Reuse manual search's legacy gallery recovery without delaying cards or
  // letting a previous response overwrite a later conversational result.
  const visibleItems = result?.page.items
  useEffect(() => {
    if (!visibleItems) return
    const controller = new AbortController()
    void Promise.all(visibleItems.map(item => hydrateIncompleteInternalGallery(item, controller.signal))).then(items => {
      if (controller.signal.aborted || items.every((item, index) => item === visibleItems[index])) return
      setResult(current => current?.page.items === visibleItems ? { ...current, page: { ...current.page, items } } : current)
    }).catch(() => { /* Recovery keeps the already usable original cover. */ })
    return () => controller.abort()
  }, [visibleItems])

  async function submit() {
    if (lock.current || needsConversation || (!pending && (!text.trim() || !modeChoice))) return
    lock.current = true
    setBusy(true)
    setNotice('Buscando opciones con condiciones confirmadas…')
    const controller = new AbortController()
    flight.current = controller
    try {
      const owned = pending || modeChoice === 'keep' ? session! : await createAISession(controller.signal,
        modeChoice === 'long' || modeChoice === 'holiday' ? modeChoice : undefined)
      setSession(owned)
      setModeChoice('keep')
      // Retry the exact operation after timeout/commit acknowledgement loss.
      // Never change text, expected version or key until a terminal response.
      const message = pending ?? { idempotency_key: crypto.randomUUID(), session_id: owned.intent.session_id,
        expected_version: owned.intent.version, text }
      setPending(message)
      const answer = await sendAIMessage(message, controller.signal)
      setRemaining(answer.operation.remaining)
      if (answer.operation.status === 'running' || answer.operation.status === 'reserved') {
        setNotice('La búsqueda sigue en curso. Consulta de nuevo el mismo intento.')
        return
      }

      if (controller.signal.aborted) return
      // Settle the durable operation before independently reading result or
      // editable-session metadata. Failed reads cannot resurrect its replay key.
      setPending(null)
      try {
        if (answer.operation.status === 'succeeded' && answer.operation.receipt && answer.cards) {
          const committed = await getAIResult(answer.operation.receipt.result_ref, controller.signal)
          if (committed.result_ref !== answer.operation.receipt.result_ref || committed.intent_hash !== answer.cards.intent_hash
            || committed.intent.session_id !== message.session_id || committed.intent.version !== message.expected_version + 1
            || committed.count !== answer.operation.receipt.count) throw new Error('Result binding mismatch')
          if (controller.signal.aborted) return
          setResult({ ref: answer.operation.receipt.result_ref, hash: answer.cards.intent_hash, committed,
            prices: answer.cards.budget_prices ?? [], page: aiCardPage(answer.cards) })
          setText('')
          setNotice('')
        } else {
          setNotice(answer.operation.failure_code === 'SESSION_VERSION_CONFLICT'
            ? 'La búsqueda cambió. Revisa tu texto antes de enviarlo de nuevo.'
            : 'Este intento no se completó. Puedes revisar el texto e intentarlo de nuevo.')
        }
        const latest = await getAISession(message.session_id, controller.signal)
        if (!controller.signal.aborted) setSession(latest)
      } catch {
        if (controller.signal.aborted) return
        setSession(null)
        setModeChoice('')
        setNeedsConversation(true)
        setNotice('El intento terminó, pero el diálogo no está disponible. Inicia una nueva conversación para continuar.')
      }
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof ApiError && [413, 422].includes(error.status)) {
        // HTTP body/schema rejection happens before operation reservation.
        setPending(null)
        setNotice('Acorta o revisa el texto antes de enviarlo de nuevo.')
      } else {
        setNotice(error instanceof ApiError && error.message === 'QUOTA_EXHAUSTED'
          ? 'Has alcanzado el límite diario. Puedes usar la búsqueda con filtros.'
          : 'No se pudo confirmar el resultado. Reintenta el mismo intento para comprobar su estado.')
      }
    } finally {
      lock.current = false
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  async function page(cursor?: string) {
    if (lock.current || !result) return
    lock.current = true
    setBusy(true)
    const controller = new AbortController()
    flight.current = controller
    try {
      const response = await aiResultPage(result.ref, cursor, controller.signal)
      if (response.intent_hash !== result.hash) throw new Error('Intent changed')
      if (!controller.signal.aborted) { setResult({ ...result, prices: response.budget_prices ?? [], page: aiCardPage(response) }); setNotice('') }
    } catch {
      if (!controller.signal.aborted) setNotice('No se pudo cargar la página. Conservamos los últimos resultados.')
    } finally { lock.current = false; if (!controller.signal.aborted) setBusy(false) }
  }

  if (!enabled) return null
  return <Dialog open={open} onOpenChange={setOpen}>
    <section className="home-ai-search" aria-label={t('Búsqueda con IA')}>
      <div className="home-ai-search__intro"><span className="home-ai-search__wave"><AudioLines aria-hidden="true" /></span><div>
        <h2>{t('¿No sabes por dónde empezar?')}</h2>
        <p>{t('Dinos dónde buscas, qué zona y qué precio quieres pagar.')}</p>
      </div></div>
      <DialogTrigger asChild><Button type="button" className="home-ai-search__action"><Search aria-hidden="true" />{t('Escribir mi búsqueda')}</Button></DialogTrigger>
      <small>{t('Describe también quién vivirá y las condiciones que necesitas.')}</small>
    </section>
    <DialogContent className="ai-search-dialog">
      <DialogHeader><DialogTitle>{t('Encuentra tu habitación')}</DialogTitle><DialogDescription>{t('Usamos condiciones confirmadas de los anuncios para buscar opciones.')}</DialogDescription></DialogHeader>
      <label htmlFor="ai-rental-mode">{t('Modo para esta búsqueda')}</label>
      <select id="ai-rental-mode" value={modeChoice} disabled={busy || pending !== null}
        onChange={event => setModeChoice(event.target.value as typeof modeChoice)}>
        <option value="" disabled>{t('Elige cómo usar el modo de alquiler')}</option>
        {session ? <option value="keep">{t('Conservar las condiciones actuales de IA')}</option> : null}
        <option value={homeMode}>{t(session ? 'Nueva conversación con el modo de inicio' : 'Usar el modo de inicio')}: {aiModeLabel(homeMode, t)}</option>
        {(modeChoice === 'long' || modeChoice === 'holiday') && modeChoice !== homeMode
          ? <option value={modeChoice}>{t('Modo de alquiler')}: {aiModeLabel(modeChoice, t)}</option> : null}
        <option value="none">{t(session ? 'Nueva conversación sin limitar el modo' : 'Sin limitar el modo de alquiler')}</option>
      </select>
      <small>{t('El modo de inicio no cambia una conversación existente. Los demás filtros no se añaden a IA.')}</small>
      {session ? <AIConditions intent={session.intent} title="Condiciones para el próximo mensaje" /> : null}
      <label htmlFor="ai-search-text">{t(result ? '¿Qué quieres cambiar?' : 'Cuéntanos qué necesitas')}</label>
      <textarea id="ai-search-text" data-i18n-exempt value={text} onChange={event => setText(event.target.value)} disabled={busy || pending !== null}
        maxLength={16000} rows={3} autoComplete="off" spellCheck={false} placeholder={t('Por ejemplo: una habitación en Madrid, hasta 700 € al mes, con mi gato.')} />
      <Button type="button" className="home-ai-search__action" disabled={busy || needsConversation || (!pending && (!text.trim() || !modeChoice || remaining === 0
        || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)))}
        onClick={() => void submit()}>{t(busy ? 'Buscando…' : pending ? 'Comprobar el mismo intento' : result ? 'Actualizar búsqueda' : 'Buscar habitaciones')}</Button>
      {(session || needsConversation) ? <Button type="button" variant="outline" disabled={busy || pending !== null}
        onClick={() => {
          if (lock.current || pending) return
          setSession(null); setNeedsConversation(false); setModeChoice(''); setMapVisible(false); setResult(null); setText(''); setNotice('')
        }}>{t('Iniciar nueva conversación')}</Button> : null}
      <div role="status" aria-live="polite">{notice ? t(notice) : null}</div>
      {remaining !== null ? <small>{t('Búsquedas disponibles hoy')}: {remaining}</small> : null}
      {result ? <section aria-label={t('Resultados confirmados')} aria-busy={busy}>
        <AIConditions intent={result.committed.intent} title="Condiciones de estos resultados" />
        <h3>{result.page.total} {t('opciones con condiciones confirmadas')}</h3>
        <p>{t('Los anuncios y su orden pueden cambiar entre páginas. Actualiza la lista para ver cambios desde el principio.')}</p>
        <Button type="button" variant="outline" disabled={busy} onClick={() => void page()}>{t('Actualizar resultados sin gastar una búsqueda')}</Button>
        {mapEnabled ? <Button type="button" variant="outline" aria-pressed={mapVisible} onClick={() => setMapVisible(value => !value)}>{t(mapVisible ? 'Ver lista' : 'Ver mapa')}</Button> : null}
        {!result.page.total ? <p>{t('No encontramos opciones con todas las condiciones confirmadas. Puedes ajustar tu búsqueda.')}</p> : null}
        {mapVisible ? <AIResultMap key={`${result.ref}:${result.hash}`} resultRef={result.ref} intentHash={result.hash} /> : null}
        <div className="ai-search-dialog__cards">{result.page.items.map(listing => {
          const price = result.prices.find(value => value.listing_id === listing.id)
          const periods = { monthly: 'por mes', weekly: 'por semana', nightly: 'por noche' } as const
          return <div key={listing.id} className="ai-search-dialog__card">
            {price && periods[price.matched_period] ? <p>{t('Precio confirmado para tu presupuesto')}: {price.matched_amount} € {t(periods[price.matched_period])}</p> : null}
            <PropertyCard listing={listing} />
          </div>
        })}</div>
        <nav aria-label={t('Páginas de resultados')}>
          <Button type="button" variant="outline" disabled={busy || !result.page.previousCursor} onClick={() => void page(result.page.previousCursor!)}>{t('Anterior')}</Button>
          <Button type="button" variant="outline" disabled={busy || !result.page.nextCursor} onClick={() => void page(result.page.nextCursor!)}>{t('Siguiente')}</Button>
        </nav>
      </section> : null}
      <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{t('Volver a los filtros')}</Button>
    </DialogContent>
  </Dialog>
}
