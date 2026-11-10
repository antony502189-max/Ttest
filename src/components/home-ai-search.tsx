import { useEffect, useRef, useState } from 'react'
import { AudioLines, Search } from 'lucide-react'
import { ApiError } from '@/api/client'
import { aiCapabilities, aiCardPage, aiMapCenter, aiResultPage, createAISession, getAIOperation, getAIQuota, getAIResult, getAISession, resetAISession, sendAIMessage, type AIBudgetPrice, type AIMessage, type AISession } from '@/api/ai-search'
import { aiConditionRows, aiModeLabel, type AICommittedIntent } from '@/api/ai-intent'
import type { RentalMode } from '@/types'
import { AIConditions } from '@/components/ai-conditions'
import { hydrateIncompleteInternalGallery, type ListingCardPage } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { PropertyCard } from '@/components/marketplace'
import { AIResultMap } from '@/components/ai-result-map'
import { PRIVATE_DEMO, PrivateDemoStatus } from '@/components/private-demo-status'
import { Button } from '@/components/ui/button'
import { AIVoiceInput } from '@/components/ai-voice-input'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import '@/home-ai-search.css'
import { readAIContinuation, storeAIContinuation } from '@/api/ai-continuation'

// Keying by identity discards private in-memory conversation on login/logout.
type AIInputPolicy = { maxLength: number; placeholder: string; hint: string; validate: (text: string) => boolean }
export function HomeAISearch({ homeMode, initialRentalMode, inputPolicy }: { homeMode: RentalMode; initialRentalMode?: RentalMode; inputPolicy?: AIInputPolicy }) {
  const { currentUser } = useApp()
  return <AISearchPanel key={currentUser?.id ?? 'guest'} identity={currentUser?.id ?? 'guest'} homeMode={homeMode} initialRentalMode={initialRentalMode} inputPolicy={inputPolicy} />
}

function AISearchPanel({ homeMode, identity, initialRentalMode, inputPolicy }: { homeMode: RentalMode; identity: string; initialRentalMode?: RentalMode; inputPolicy?: AIInputPolicy }) {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)
  const [mapEnabled, setMapEnabled] = useState(false)
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [recording, setRecording] = useState(false)
  const [mapVisible, setMapVisible] = useState(false)
  const [mapRefreshVersion, setMapRefreshVersion] = useState(0)
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const invalidText = Boolean(inputPolicy && text && !inputPolicy.validate(text))
  const [session, setSession] = useState<AISession | null>(null)
  const [modeChoice, setModeChoice] = useState<'' | 'keep' | 'none' | RentalMode>(initialRentalMode ?? '')
  const [needsConversation, setNeedsConversation] = useState(false)
  const [pending, setPending] = useState<AIMessage | null>(null)
  const [result, setResult] = useState<{ ref: string; hash: string; committed: AICommittedIntent; prices: AIBudgetPrice[]; center?: { lat: number; lng: number }; page: ListingCardPage } | null>(null)
  const [resultInvalid, setResultInvalid] = useState(false)
  const [remaining, setRemaining] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [demoBlocked, setDemoBlocked] = useState(PRIVATE_DEMO)
  const [demoReason, setDemoReason] = useState('Проверяем доступ к голосовому поиску…')
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
  // Independent of in-memory raw payload. The durable locator is written
  // synchronously before POST, and retained until receipt hydration succeeds.
  const operationLocator = useRef<import('@/api/ai-continuation').AIOperationLocator | null>(null)
  const restoreTranslate = useRef(t)
  restoreTranslate.current = t

  useEffect(() => {
    if (!text || pending) return
    const timer = window.setTimeout(() => setText(''), 15 * 60 * 1000)
    return () => window.clearTimeout(timer)
  }, [text, pending])

  useEffect(() => {
    if (!pending?.audio_base64) return
    // Retain only the durable operation locator after this in-memory retry
    // window. Reload/sync recovers a receipt without persisting or resending audio.
    const timer = window.setTimeout(() => {
      flight.current?.abort(); setPending(null); setBusy(false)
      setRestoring(true); setRestoreEpoch(value => value + 1)
    }, 15 * 60 * 1000)
    return () => window.clearTimeout(timer)
  }, [pending])

  useEffect(() => {
    const saved = readAIContinuation(identity)
    if (!saved) { operationLocator.current = null; lock.current = false; setRestoring(false); return }
    const controller = new AbortController()
    syncFlight.current?.abort()
    setRestoring(true)
    lock.current = true
    void (async () => {
      try {
        // Neither storage nor the former UI state grants access. Validate every
        // locator against today's cookie/bearer and current session lifetime.
        let resultRef = saved.resultRef
        let receipt: { result_ref: string; count: number } | null = null
        let failedOperation = false
        if (saved.operation) {
          operationLocator.current = saved.operation
          const status = await getAIOperation(saved.operation.key, controller.signal)
          if (controller.signal.aborted) return
          if (status.idempotency_key !== saved.operation.key) throw new Error('Operation binding mismatch')
          setRemaining(status.remaining)
          if (status.status === 'running' || status.status === 'reserved') {
            setRestoreFailed(true)
            setNotice('La búsqueda sigue en curso. Consulta de nuevo el mismo intento.')
            return
          }
          if (status.status === 'succeeded') {
            if (!status.receipt) throw new Error('Missing operation receipt')
            receipt = status.receipt
            resultRef = receipt.result_ref
          } else {
            failedOperation = true
            operationLocator.current = null
            storeAIContinuation(identity, { sessionId: saved.sessionId })
            setNotice('Este intento no se completó. Puedes revisar el texto e intentarlo de nuevo.')
          }
        }
        const owned = await getAISession(saved.sessionId, controller.signal)
        if (controller.signal.aborted) return
        setSession(owned); setModeChoice('keep'); setNeedsSync(false); setSyncingSession(false)
        if (resultRef) {
          const committed = await getAIResult(resultRef, controller.signal)
          if (committed.intent.session_id !== saved.sessionId || committed.result_ref !== resultRef ||
            (receipt && (committed.count !== receipt.count || committed.intent.version !== saved.operation!.expectedVersion + 1)))
            throw new Error('Result session mismatch')
          const response = await aiResultPage(resultRef, undefined, controller.signal)
          if (response.intent_hash !== committed.intent_hash || aiConditionRows(committed.intent, restoreTranslate.current) === null)
            throw new Error('Result binding mismatch')
          if (controller.signal.aborted) return
          setResult({ ref: committed.result_ref, hash: committed.intent_hash, committed,
            prices: response.budget_prices ?? [], center: aiMapCenter(response), page: aiCardPage(response) })
          setPagingAvailable(true); setResultInvalid(false)
        }
        operationLocator.current = null
        storeAIContinuation(identity, { sessionId: saved.sessionId, ...(resultRef ? { resultRef } : {}) })
        setRestoreFailed(false)
        setNotice(failedOperation ? 'Este intento no se completó. Puedes revisar el texto e intentarlo de nuevo.' : '')
      } catch (error) {
        if (!controller.signal.aborted) {
          if ((error instanceof ApiError && (error.status === 0 || error.status === 429 || error.status >= 500 ||
            (saved.operation && error.status === 404 && error.message === 'OPERATION_NOT_FOUND'))) ||
            (saved.operation && !(error instanceof ApiError))) {
            setRestoreFailed(true)
            setNotice('No se pudo actualizar el diálogo. Conservamos tu búsqueda. Reintenta la sincronización.')
          } else {
            storeAIContinuation(identity, null)
            operationLocator.current = null
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
      ? { sessionId: session.intent.session_id, ...(result && pagingAvailable ? { resultRef: result.ref } : {}),
        ...(operationLocator.current ? { operation: operationLocator.current } : {}) } : null)
  }, [identity, restoring, restoreFailed, session, result, pagingAvailable, needsConversation, pending])

  useEffect(() => {
    const controller = new AbortController()
    void aiCapabilities(controller.signal).then(value => {
      if (!controller.signal.aborted) { setEnabled(value.text === true); setMapEnabled(value.map === true); setVoiceEnabled(value.voice === true) }
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
    if (!visibleItems || inputPolicy) return
    const controller = new AbortController()
    void Promise.all(visibleItems.map(item => hydrateIncompleteInternalGallery(item, controller.signal))).then(items => {
      if (controller.signal.aborted || items.every((item, index) => item === visibleItems[index])) return
      setResult(current => current?.page.items === visibleItems ? { ...current, page: { ...current.page, items } } : current)
    }).catch(() => { /* Recovery keeps the already usable original cover. */ })
    return () => controller.abort()
  }, [visibleItems, inputPolicy])

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
      const fresh = await changeSession(session && !needsConversation ? session : null, controller.signal, initialRentalMode)
      if (controller.signal.aborted) return
      setSession(fresh)
      setNeedsConversation(false)
      setModeChoice(initialRentalMode ? 'keep' : '')
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

  async function submit(audio?: string) {
    if (restoring || restoreFailed || lock.current || (!pending && !audio && invalidText) || (!pending && (demoBlocked || remaining === 0 || (changingSession && session !== null) || needsConversation || needsSync || syncingSession || (!audio && !text.trim()) || !modeChoice || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)))) return
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
        expected_version: owned.intent.version, text: audio ? '' : text, ...(audio ? { audio_base64: audio } : {}) }
      operationLocator.current ??= { key: message.idempotency_key, expectedVersion: message.expected_version, createdAt: Date.now() }
      storeAIContinuation(identity, { sessionId: message.session_id, operation: operationLocator.current })
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
      if (answer.operation.status === 'failed') operationLocator.current = null
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
            prices: answer.cards.budget_prices ?? [], center: aiMapCenter(answer.cards), page: aiCardPage(answer.cards) })
          operationLocator.current = null
          storeAIContinuation(identity, { sessionId: message.session_id, resultRef: committed.result_ref })
          setText('')
          setNotice('')
        } catch (error) {
          if (controller.signal.aborted) return
          staleResults()
          if (!(error instanceof ApiError) || error.status === 0 || error.status === 429 || error.status >= 500) {
            setRestoreFailed(true)
            setNotice('No se pudo actualizar el diálogo. Conservamos tu búsqueda. Reintenta la sincronización.')
          } else operationLocator.current = null
        }
      } else {
        operationLocator.current = null
        const questions: Record<string, string> = {
          budget_period: '¿El presupuesto es por noche, semana o mes?',
          rental_mode: '¿Buscas alquiler vacacional o de larga duración?',
          balcony_requirement: '¿Necesitas un balcón privado o también sirve una terraza compartida?',
          location: '¿En qué localidad o zona quieres buscar?',
          dates: '¿Qué fechas necesitas?',
          unsupported: inputPolicy?.hint ?? 'Reformula la petición con ubicación, presupuesto y requisitos de la vivienda.',
        }
        const code = answer.operation.failure_code
        setNotice(answer.clarification ? questions[answer.clarification]
          : code === 'INTENT_CLARIFICATION_REQUIRED' ? 'Aclara la ubicación, el presupuesto o los requisitos antes de continuar.'
          : code === 'INTENT_NO_CHANGE' ? 'La petición no cambia los criterios. Añade un requisito nuevo.'
          : code === 'INTENT_UNSUPPORTED' ? (message.audio_base64 ? 'Не удалось разобрать бюджет из записи. Повторите или введите его текстом. Поиск не списан.' : questions.unsupported)
          : code === 'SOURCE_COVERAGE_UNAVAILABLE' ? (inputPolicy ? 'Каталог устарел или недоступен. Новые обращения к модели остановлены до проверки данных.' : 'No hay fuentes verificadas recientes disponibles. Prueba la búsqueda con filtros.')
          : code === 'ASR_FAILURE' ? 'Не удалось распознать запись. Повторите или введите запрос текстом. Поиск не списан.'
          : code === 'VOICE_CAPACITY_LIMIT' ? 'Сервер распознавания занят. Повторите запись позже. Поиск не списан.'
          : code === 'SESSION_VERSION_CONFLICT'
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
        operationLocator.current = null
        // Authentication failed before reservation. An old owner cannot be
        // replayed under a renewed guest identity; keep only draft/results.
        setPending(null)
        lostConversation()
      } else if (error instanceof ApiError && error.status === 429 && error.message === 'QUOTA_EXHAUSTED') {
        operationLocator.current = null
        // Only this exact code proves reserve rejected before inserting a row.
        setPending(null)
        setRemaining(0)
        setNotice('Has alcanzado el límite diario. Puedes usar la búsqueda con filtros.')
      } else if (error instanceof ApiError && ([413, 422].includes(error.status)
        || (error.status === 400 && error.message === 'AI_REQUEST_INVALID' && Boolean(audio || pending?.audio_base64)))) {
        operationLocator.current = null
        // HTTP body/schema rejection happens before operation reservation.
        setPending(null)
        setNotice(error.status === 400 ? 'Запись отклонена до начала поиска. Запишите запрос заново или введите текст. Поиск не списан.'
          : 'Acorta o revisa el texto antes de enviarlo de nuevo.')
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
      if (!controller.signal.aborted) {
        setResult({ ...result, prices: response.budget_prices ?? [], center: aiMapCenter(response), page: aiCardPage(response) })
        // A result reference freezes conditions, not catalog membership. An
        // explicit first-page refresh must also invalidate the viewport read.
        if (!cursor) setMapRefreshVersion(value => value + 1)
        setNotice('')
      }
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
        <p>{inputPolicy ? inputPolicy.hint : t('Dinos dónde buscas, qué zona y qué precio quieres pagar.')}</p>
      </div></div>
      <DialogTrigger asChild><Button type="button" className="home-ai-search__action"><Search aria-hidden="true" />{t('Escribir mi búsqueda')}</Button></DialogTrigger>
      {voiceEnabled ? <DialogTrigger asChild><Button type="button" variant="outline"><AudioLines aria-hidden="true" />{t('Buscar con la voz')}</Button></DialogTrigger> : null}
      {!inputPolicy ? <small>{t('Describe también quién vivirá y las condiciones que necesitas.')}</small> : null}
    </section>
    <DialogContent className="ai-search-dialog">
      <DialogHeader><DialogTitle>{t('Encuentra tu habitación')}</DialogTitle><DialogDescription>{t('Usamos condiciones confirmadas de los anuncios para buscar opciones.')}</DialogDescription></DialogHeader>
      <PrivateDemoStatus refreshKey={`${session?.intent.version ?? 0}:${busy}`} onBlocked={setDemoBlocked} onReason={setDemoReason} />
      {import.meta.env.VITE_AI_CLOSED_LAB ? <p data-ai-lab-mode={import.meta.env.VITE_AI_CLOSED_LAB}>
        {t(import.meta.env.VITE_AI_CLOSED_LAB === 'closed-live-synthetic'
          ? 'Prueba cerrada con modelo real y catálogo simulado. Usa solo las frases sintéticas autorizadas. No envíes datos personales.'
          : 'Prueba cerrada con datos y respuestas simuladas. No envíes datos personales.')}
      </p> : null}
      <label htmlFor="ai-rental-mode">{t('Modo para esta búsqueda')}</label>
      <select id="ai-rental-mode" value={modeChoice} disabled={recording || busy || restoring || restoreFailed || pending !== null || changingSession}
        onChange={event => setModeChoice(event.target.value as typeof modeChoice)}>
        <option value="" disabled>{t('Elige cómo usar el modo de alquiler')}</option>
        {session ? <option value="keep">{t('Conservar las condiciones actuales de IA')}</option> : null}
        <option value={homeMode}>{t(session ? 'Nueva conversación con el modo de inicio' : 'Usar el modo de inicio')}: {aiModeLabel(homeMode, t)}</option>
        <option value={homeMode === 'long' ? 'holiday' : 'long'}>{t('Modo de alquiler')}: {aiModeLabel(homeMode === 'long' ? 'holiday' : 'long', t)}</option>
        <option value="none">{t(session ? 'Nueva conversación sin limitar el modo' : 'Sin limitar el modo de alquiler')}</option>
      </select>
      <small>{t('El modo de inicio no cambia una conversación existente. Los demás filtros no se añaden a IA.')}</small>
      {session ? <AIConditions intent={session.intent} title="Condiciones para el próximo mensaje" /> : null}
      <label htmlFor="ai-search-text">{t(result ? '¿Qué quieres cambiar?' : 'Cuéntanos qué necesitas')}</label>
      <textarea id="ai-search-text" data-i18n-exempt value={text} onChange={event => setText(event.target.value)} disabled={recording || busy || restoring || pending !== null}
        maxLength={inputPolicy?.maxLength ?? 16000} rows={3} autoComplete="off" spellCheck={false} placeholder={inputPolicy?.placeholder ?? t('Por ejemplo: una habitación en Madrid, hasta 700 € al mes, con mi gato.')} />
      {inputPolicy ? <p role={invalidText ? 'alert' : undefined} data-i18n-exempt>{inputPolicy.hint}</p> : null}
      {voiceEnabled ? <AIVoiceInput disabled={busy || restoring || restoreFailed || demoBlocked || pending !== null || changingSession || syncingSession || needsSync || needsConversation || !modeChoice || remaining === 0 || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)}
        disabledReason={busy ? 'Обрабатываем запрос и ищем варианты…' : demoBlocked ? demoReason : remaining === 0 ? 'Лимит запросов исчерпан. Повторите после его обновления.' : !modeChoice ? 'Выберите режим аренды перед записью.' : restoreFailed ? 'Не удалось восстановить поиск. Повторите восстановление.' : pending ? 'Ответ не подтверждён. Нажмите «Проверить результат попытки» ниже.' : 'Дождитесь завершения текущей операции и синхронизации поиска.'}
        onAudio={audio => void submit(audio)} onRecording={setRecording} /> : null}
      <Button type="button" className="home-ai-search__action" disabled={recording || busy || restoring || restoreFailed || (!pending && (invalidText || demoBlocked || (changingSession && session !== null) || syncingSession || needsSync || needsConversation || !text.trim() || !modeChoice || remaining === 0 || (modeChoice === 'keep' && session !== null && aiConditionRows(session.intent, t) === null)))}
        onClick={() => void submit()}>{PRIVATE_DEMO && pending && !busy ? <span data-i18n-exempt>Проверить результат попытки</span> : t(busy ? 'Buscando…' : pending ? 'Comprobar el mismo intento' : result ? 'Actualizar búsqueda' : 'Buscar habitaciones')}</Button>
      {busy && pending ? <Button type="button" variant="outline" onClick={() => {
        flight.current?.abort(); setBusy(false)
        setNotice('No se pudo confirmar el resultado. Reintenta el mismo intento para comprobar su estado.')
      }}>{t('Dejar de esperar')}</Button> : null}
      {restoreFailed ? <Button type="button" variant="outline" disabled={restoring} onClick={() => {
        setRestoring(true); setRestoreFailed(false); setRestoreEpoch(value => value + 1)
      }}>{t('Reintentar sincronización')}</Button> : null}
      {(session || needsConversation || changingSession) ? <Button type="button" variant="outline" disabled={recording || busy || restoreFailed || syncingSession || needsSync || pending !== null}
        onClick={() => void newConversation()}>{t('Iniciar nueva conversación')}</Button> : null}
      {needsSync && session && !restoreFailed ? <Button type="button" variant="outline" disabled={syncingSession || busy}
        onClick={() => void refreshSession(session.intent.session_id, true)}>{t('Reintentar sincronización')}</Button> : null}
      {result && !pagingAvailable && !resultInvalid ? <p>{t('Los resultados anteriores siguen visibles. Inicia una nueva búsqueda para ver más páginas.')}</p> : null}
      <div role="status" aria-live="polite">{notice ? t(notice) : null}</div>
      {remaining !== null ? <small>{t('Búsquedas disponibles hoy')}: {remaining}</small> : null}
      {result ? <section aria-label={t('Resultados confirmados')} aria-busy={busy}>
        <p>{t('Solo mostramos opciones con datos verificados recientes. Puede haber fuentes sin verificar; los resultados no cubren todo el mercado.')}</p>
        <p>{t('La lista y el mapa se actualizan por separado. Los anuncios pueden cambiar entre ambas lecturas; el mapa solo muestra la zona visible.')}</p>
        <AIConditions intent={result.committed.intent} title="Condiciones de estos resultados" />
        {!resultInvalid ? <>
        <h3>{result.page.total} {t('opciones con condiciones confirmadas')}</h3>
        <p>{t('Los anuncios y su orden pueden cambiar entre páginas. Actualiza la lista para ver cambios desde el principio.')}</p>
        <Button type="button" variant="outline" disabled={busy || changingSession || pending !== null || !pagingAvailable} onClick={() => void page()}>{t('Actualizar resultados sin gastar una búsqueda')}</Button>
        {mapEnabled ? <Button type="button" variant="outline" aria-pressed={mapVisible} onClick={() => setMapVisible(value => !value)}>{t(mapVisible ? 'Ver lista' : 'Ver mapa')}</Button> : null}
        {!result.page.total ? <p>{t('No encontramos opciones con todas las condiciones confirmadas. Puedes ajustar tu búsqueda.')}</p> : null}
        {mapVisible ? <AIResultMap key={`${result.ref}:${result.hash}`} resultRef={result.ref} intentHash={result.hash} refreshVersion={mapRefreshVersion}
          center={result.center} total={result.page.total} /> : null}
        <div className="ai-search-dialog__cards" hidden={mapVisible} style={{ display: mapVisible ? 'none' : undefined }}>{result.page.items.map(listing => {
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
