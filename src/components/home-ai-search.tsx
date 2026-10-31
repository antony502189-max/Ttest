import { useEffect, useRef, useState } from 'react'
import { AudioLines, Search } from 'lucide-react'
import { ApiError } from '@/api/client'
import { aiCapabilities, aiCardPage, aiResultPage, createAISession, getAIQuota, getAIResult, getAISession, resetAISession, sendAIMessage, type AIBudgetPrice, type AIMessage, type AISession } from '@/api/ai-search'
import { aiConditionRows, aiModeLabel, type AICommittedIntent } from '@/api/ai-intent'
import type { RentalMode } from '@/types'
import { AIConditions } from '@/components/ai-conditions'
import { hydrateIncompleteInternalGallery, type ListingCardPage } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { PropertyCard } from '@/components/marketplace'
import { AIResultMap } from '@/components/ai-result-map'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import '@/home-ai-search.css'
import { readAIContinuation, storeAIContinuation } from '@/api/ai-continuation'

// Keying by identity discards private in-memory conversation on login/logout.
export function HomeAISearch({ homeMode }: { homeMode: RentalMode }) {
  const { currentUser } = useApp()
  return <AISearchPanel key={currentUser?.id ?? 'guest'} identity={currentUser?.id ?? 'guest'} homeMode={homeMode} />
}

function AISearchPanel({ homeMode, identity }: { homeMode: RentalMode; identity: string }) {
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
  const [resultInvalid, setResultInvalid] = useState(false)
  const [remaining, setRemaining] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [syncingSession, setSyncingSession] = useState(false)
  const [needsSync, setNeedsSync] = useState(false)
  const [pagingAvailable, setPagingAvailable] = useState(true)
  const syncFlight = useRef<AbortController | null>(null)
  const [notice, setNotice] = useState('')
  const flight = useRef<AbortController | null>(null)
  const lock = useRef(false)
  const command = useRef<{ key: string; source: AISession | null; mode?: RentalMode } | null>(null)
  const [changingSession, setChangingSession] = useState(false)
  const [restoring, setRestoring] = useState(true)
  const [restoreFailed, setRestoreFailed] = useState(false)
  const [restoreEpoch, setRestoreEpoch] = useState(0)
  const restoreTranslate = useRef(t)
  restoreTranslate.current = t

  useEffect(() => {
    const saved = readAIContinuation(identity)
    if (!saved) { lock.current = false; setRestoring(false); return }
    const controller = new AbortController()
    setRestoring(true)
    lock.current = true
    void (async () => {
      try {
        // Neither storage nor the former UI state grants access. Validate every
        // locator against today's cookie/bearer and current session lifetime.
        const owned = await getAISession(saved.sessionId, controller.signal)
        if (controller.signal.aborted) return
        setSession(owned); setModeChoice('keep')
        if (saved.resultRef) {
          const committed = await getAIResult(saved.resultRef, controller.signal)
          if (committed.intent.session_id !== saved.sessionId) throw new Error('Result session mismatch')
          const response = await aiResultPage(saved.resultRef, undefined, controller.signal)
          if (response.intent_hash !== committed.intent_hash || aiConditionRows(committed.intent, restoreTranslate.current) === null)
            throw new Error('Result binding mismatch')
          if (controller.signal.aborted) return
          setResult({ ref: committed.result_ref, hash: committed.intent_hash, committed,
            prices: response.budget_prices ?? [], page: aiCardPage(response) })
        }
        setRestoreFailed(false); setNotice('')
      } catch (error) {
        if (!controller.signal.aborted) {
          if (error instanceof ApiError && (error.status === 0 || error.status === 429 || error.status >= 500)) {
            setRestoreFailed(true)
            setNotice('No se pudo actualizar el diálogo. Conservamos tu búsqueda. Reintenta la sincronización.')
          } else {
            storeAIContinuation(identity, null)
            // No cached cards or substitution of the editable intent for a
            // failed committed-result read. Explicit new search stays available.
            setResult(null)
          }
        }
      } finally {
        if (!controller.signal.aborted) { lock.current = false; setRestoring(false) }
      }
    })()
    return () => controller.abort()
  }, [identity, restoreEpoch])

  useEffect(() => {
    if (!restoring && !restoreFailed) storeAIContinuation(identity, session && !needsConversation
      ? { sessionId: session.intent.session_id, ...(result && pagingAvailable ? { resultRef: result.ref } : {}) } : null)
  }, [identity, restoring, restoreFailed, session, result, pagingAvailable, needsConversation])

  useEffect(() => {
    const controller = new AbortController()
    void aiCapabilities(controller.signal).then(value => {
      if (!controller.signal.aborted) { setEnabled(value.text === true); setMapEnabled(value.map === true) }
    }).catch(() => { /* Ordinary search stays available when capability lookup fails. */ })
    return () => { controller.abort(); flight.current?.abort(); syncFlight.current?.abort() }
  }, [])

  const ownedSessionId = session?.intent.session_id
  useEffect(() => {
    if (!open || busy) return
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

  function unavailable(error: unknown) {
    return error instanceof ApiError && (
      (error.status === 409 && error.message === 'SESSION_EXPIRED') ||
      (error.status === 404 && error.message === 'SESSION_NOT_FOUND') ||
      (error.status === 401 && ['AI_GUEST_IDENTITY_INVALID_OR_EXPIRED', 'AI_GUEST_IDENTITY_REQUIRED'].includes(error.message)))
  }

  function guestIdentityLost(error: unknown) {
    return error instanceof ApiError && error.status === 401 &&
      ['AI_GUEST_IDENTITY_INVALID_OR_EXPIRED', 'AI_GUEST_IDENTITY_REQUIRED'].includes(error.message)
  }

  function staleResults() {
    setResultInvalid(true)
    setPagingAvailable(false)
    setNotice('Los resultados ya no están disponibles. Repite la búsqueda para obtener páginas nuevas.')
  }

  function forgetCommand() {
    command.current = null
    setChangingSession(false)
  }

  async function changeSession(source: AISession | null, signal: AbortSignal, mode?: RentalMode) {
    // Preserve exact key, source and version through ambiguous HTTP failures.
    const attempt = command.current ?? { key: crypto.randomUUID(), source, mode }
    command.current = attempt
    setChangingSession(true)
    const fresh = attempt.source
      ? await resetAISession(attempt.source, attempt.key, signal, attempt.mode)
      : await createAISession(attempt.key, signal, attempt.mode)
    forgetCommand()
    return fresh
  }

  function lostConversation() {
    setResultInvalid(true)
    forgetCommand()
    setNeedsConversation(true)
    setNeedsSync(false)
    setPagingAvailable(false)
    setNotice('El intento terminó, pero el diálogo no está disponible. Inicia una nueva conversación para continuar.')
  }

  async function refreshSession(id: string, clearNotice = false) {
    syncFlight.current?.abort()
    const controller = new AbortController()
    syncFlight.current = controller
    setSyncingSession(true)
    setNeedsSync(true)
    try {
      const latest = await getAISession(id, controller.signal)
      if (controller.signal.aborted) return
      setSession(latest)
      setNeedsSync(false)
      if (clearNotice) setNotice('')
    } catch (error) {
      if (controller.signal.aborted) return
      if (unavailable(error)) lostConversation()
      else setNotice('No se pudo actualizar el diálogo. Conservamos tu búsqueda. Reintenta la sincronización.')
    } finally {
      if (!controller.signal.aborted) setSyncingSession(false)
    }
  }

  async function newConversation() {
    if (restoring || restoreFailed || lock.current || pending || syncingSession || needsSync) return
    lock.current = true
    setBusy(true)
    const controller = new AbortController()
    flight.current = controller
    try {
      const fresh = await changeSession(session && !needsConversation ? session : null, controller.signal)
      if (controller.signal.aborted) return
      setSession(fresh)
      setNeedsConversation(false)
      setModeChoice('')
      setPagingAvailable(false)
      setNotice(result ? 'Nueva conversación lista. Conservamos los resultados anteriores hasta tu próxima búsqueda.' : '')
      // Draft and cards stay in memory, including when server transition fails.
    } catch (error) {
      if (controller.signal.aborted) return
      if (unavailable(error)) lostConversation()
      else if (error instanceof ApiError && ['SESSION_VERSION_CONFLICT', 'SESSION_COMMAND_CONFLICT'].includes(error.message) && session) {
        forgetCommand()
        void refreshSession(session.intent.session_id)
      } else setNotice(error instanceof ApiError && error.message === 'SESSION_LIMIT'
        ? 'Hay demasiadas conversaciones activas. Conservamos tu texto y resultados. Inténtalo más tarde.'
        : 'No se pudo iniciar una nueva conversación. Conservamos tu texto y resultados.')
    } finally {
      lock.current = false
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  async function submit() {
    if (restoring || restoreFailed || lock.current || (!pending && ((changingSession && session !== null) || needsConversation || needsSync || syncingSession || !text.trim() || !modeChoice || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)))) return
    lock.current = true
    setBusy(true)
    setNotice('Buscando opciones con condiciones confirmadas…')
    const controller = new AbortController()
    flight.current = controller
    try {
      const owned = (pending || modeChoice === 'keep') && session ? session : await changeSession(
        session && !needsConversation ? session : null, controller.signal,
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
      // A durable terminal answer settles the operation even when its editable
      // session has expired. Only ambiguous responses retain the replay key.
      setPending(null)
      if (answer.operation.status === 'succeeded' && answer.operation.receipt && answer.cards) {
        try {
          const committed = await getAIResult(answer.operation.receipt.result_ref, controller.signal)
          if (committed.result_ref !== answer.operation.receipt.result_ref || committed.intent_hash !== answer.cards.intent_hash
            || committed.intent.session_id !== message.session_id || committed.intent.version !== message.expected_version + 1
            || committed.count !== answer.operation.receipt.count) throw new Error('Result binding mismatch')
          if (controller.signal.aborted) return
          setPagingAvailable(true)
          setResultInvalid(false)
          setResult({ ref: answer.operation.receipt.result_ref, hash: answer.cards.intent_hash, committed,
            prices: answer.cards.budget_prices ?? [], page: aiCardPage(answer.cards) })
          setText('')
          setNotice('')
        } catch {
          if (controller.signal.aborted) return
          staleResults()
        }
      } else {
        setNotice(answer.operation.failure_code === 'SESSION_VERSION_CONFLICT'
          ? 'La búsqueda cambió. Revisa tu texto antes de enviarlo de nuevo.'
          : 'Este intento no se completó. Puedes revisar el texto e intentarlo de nuevo.')
      }
      // Missing cards do not prove the editable conversation disappeared.
      if (answer.cards_error) staleResults()
      // Independent read phase; version-sensitive actions wait for sync.
      void refreshSession(message.session_id)
    } catch (error) {
      if (controller.signal.aborted) return
      if (guestIdentityLost(error)) {
        // Authentication failed before reservation. An old owner cannot be
        // replayed under a renewed guest identity; keep only draft/results.
        setPending(null)
        lostConversation()
      } else if (error instanceof ApiError && error.status === 429 && error.message === 'QUOTA_EXHAUSTED') {
        // Only this exact code proves reserve rejected before inserting a row.
        setPending(null)
        setRemaining(0)
        setNotice('Has alcanzado el límite diario. Puedes usar la búsqueda con filtros.')
      } else if (error instanceof ApiError && [413, 422].includes(error.status)) {
        // HTTP body/schema rejection happens before operation reservation.
        setPending(null)
        setNotice('Acorta o revisa el texto antes de enviarlo de nuevo.')
      } else if (command.current) {
        if (unavailable(error)) lostConversation()
        else setNotice('No se pudo iniciar una nueva conversación. Conservamos tu texto y resultados.')
      } else {
        setNotice('No se pudo confirmar el resultado. Reintenta el mismo intento para comprobar su estado.')
      }
    } finally {
      lock.current = false
      if (!controller.signal.aborted) setBusy(false)
    }
  }

  async function page(cursor?: string) {
    if (lock.current || changingSession || pending || !result || !pagingAvailable) return
    lock.current = true
    setBusy(true)
    const controller = new AbortController()
    flight.current = controller
    try {
      const response = await aiResultPage(result.ref, cursor, controller.signal)
      if (response.intent_hash !== result.hash) throw new ApiError(409, 'AI_REQUERY_REQUIRED')
      if (!controller.signal.aborted) { setResult({ ...result, prices: response.budget_prices ?? [], page: aiCardPage(response) }); setNotice('') }
    } catch (error) {
      if (!controller.signal.aborted) {
        if (unavailable(error)) lostConversation()
        else if (error instanceof ApiError && ['AI_REQUERY_REQUIRED', 'RESULT_NOT_FOUND', 'RESULT_EXPIRED_REQUERY_REQUIRED'].includes(error.message)) {
          staleResults()
          if (error.message !== 'AI_REQUERY_REQUIRED' && session) void refreshSession(session.intent.session_id)
        } else setNotice('No se pudo cargar la página. Conservamos los últimos resultados.')
      }
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
      <select id="ai-rental-mode" value={modeChoice} disabled={busy || restoring || pending !== null || changingSession}
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
      <textarea id="ai-search-text" data-i18n-exempt value={text} onChange={event => setText(event.target.value)} disabled={busy || restoring || pending !== null}
        maxLength={16000} rows={3} autoComplete="off" spellCheck={false} placeholder={t('Por ejemplo: una habitación en Madrid, hasta 700 € al mes, con mi gato.')} />
      <Button type="button" className="home-ai-search__action" disabled={busy || restoring || restoreFailed || (!pending && ((changingSession && session !== null) || syncingSession || needsSync || needsConversation || !text.trim() || !modeChoice || remaining === 0 || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)))}
        onClick={() => void submit()}>{t(busy ? 'Buscando…' : pending ? 'Comprobar el mismo intento' : result ? 'Actualizar búsqueda' : 'Buscar habitaciones')}</Button>
      {busy && pending ? <Button type="button" variant="outline" onClick={() => {
        flight.current?.abort(); setBusy(false)
        setNotice('No se pudo confirmar el resultado. Reintenta el mismo intento para comprobar su estado.')
      }}>{t('Cancelar')}</Button> : null}
      {restoreFailed ? <Button type="button" variant="outline" disabled={restoring} onClick={() => {
        setRestoring(true); setRestoreFailed(false); setRestoreEpoch(value => value + 1)
      }}>{t('Reintentar sincronización')}</Button> : null}
      {(session || needsConversation || changingSession) ? <Button type="button" variant="outline" disabled={busy || syncingSession || needsSync || pending !== null}
        onClick={() => void newConversation()}>{t('Iniciar nueva conversación')}</Button> : null}
      {needsSync && session ? <Button type="button" variant="outline" disabled={syncingSession || busy}
        onClick={() => void refreshSession(session.intent.session_id, true)}>{t('Reintentar sincronización')}</Button> : null}
      {result && !pagingAvailable && !resultInvalid ? <p>{t('Los resultados anteriores siguen visibles. Inicia una nueva búsqueda para ver más páginas.')}</p> : null}
      <div role="status" aria-live="polite">{notice ? t(notice) : null}</div>
      {remaining !== null ? <small>{t('Búsquedas disponibles hoy')}: {remaining}</small> : null}
      {result ? <section aria-label={t('Resultados confirmados')} aria-busy={busy}>
        <AIConditions intent={result.committed.intent} title="Condiciones de estos resultados" />
        {!resultInvalid ? <>
        <h3>{result.page.total} {t('opciones con condiciones confirmadas')}</h3>
        <p>{t('Los anuncios y su orden pueden cambiar entre páginas. Actualiza la lista para ver cambios desde el principio.')}</p>
        <Button type="button" variant="outline" disabled={busy || changingSession || pending !== null || !pagingAvailable} onClick={() => void page()}>{t('Actualizar resultados sin gastar una búsqueda')}</Button>
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
        </> : null}
        <nav aria-label={t('Páginas de resultados')}>
          <Button type="button" variant="outline" disabled={busy || changingSession || pending !== null || !pagingAvailable || !result.page.previousCursor} onClick={() => void page(result.page.previousCursor!)}>{t('Anterior')}</Button>
          <Button type="button" variant="outline" disabled={busy || changingSession || pending !== null || !pagingAvailable || !result.page.nextCursor} onClick={() => void page(result.page.nextCursor!)}>{t('Siguiente')}</Button>
        </nav>
      </section> : null}
      <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{t('Volver a los filtros')}</Button>
    </DialogContent>
  </Dialog>
}
