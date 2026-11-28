import { expect, test, type Page } from '@playwright/test'

const userId = '00000000-0000-4000-8000-000000000011'
const sid = '00000000-0000-4000-8000-000000000021', ref = '00000000-0000-4000-8000-000000000022'
const guestSid = '00000000-0000-4000-8000-000000000031', guestRef = '00000000-0000-4000-8000-000000000032'
const user = { id: userId, name: 'Native Account', email: 'synthetic@example.test', role: 'tenant', initials: 'NA', phone: '', whatsapp: '', telegram: '', about: '', showPhone: false, showWhatsApp: false, emailVerified: true }

for (const locale of [
  { language: 'es', open: 'Buscar con mi voz', mic: 'Grabar búsqueda', textAction: 'Buscar', dictate: 'Dictar búsqueda', recording: 'Grabando…', cancel: 'Cancelar grabación', denied: 'Permite el acceso al micrófono en el navegador.', guide: 'Qué puedes indicar', close: 'Cerrar', nightly: 'Estudio en Madrid hasta 70 euros por noche, amueblado' },
  { language: 'ru', open: 'Искать голосом', mic: 'Записать запрос', textAction: 'Поиск', dictate: 'Надиктовать запрос', recording: 'Идёт запись…', cancel: 'Отменить запись', denied: 'Разрешите доступ к микрофону в браузере.', guide: 'Что можно указать', close: 'Закрыть', nightly: 'Студия в Мадриде до 70 евро за ночь, с мебелью' },
  { language: 'en', open: 'Search with my voice', mic: 'Record search', textAction: 'Search', dictate: 'Dictate search', recording: 'Recording…', cancel: 'Cancel recording', denied: 'Allow microphone access in your browser.', guide: 'What you can include', close: 'Close', nightly: 'A studio in Madrid under 70 euros per night, furnished' },
]) test(`native search ${locale.language}: mobile guidance and microphone recovery without a query`, async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  const state = await surface(page, false, locale.language)
  await page.goto('/#/')
  await page.getByRole('button', { name: locale.open, exact: true }).click()
  const dialog = page.getByRole('dialog')
  const guide = dialog.getByRole('region', { name: locale.guide })
  await expect(guide).toBeVisible()
  await expect(guide.locator('dt')).toHaveCount(4)
  await expect(dialog.getByRole('button', { name: locale.close, exact: true })).toBeVisible()
  await dialog.locator('#ai-rental-mode').selectOption('holiday')
  await expect(guide.getByText(locale.nightly, { exact: true })).toBeVisible()
  const draft = dialog.locator('#ai-search-text')
  await expect(draft).toHaveCount(0)
  expect(await dialog.evaluate(node => node.scrollWidth)).toBe(await dialog.evaluate(node => node.clientWidth))
  await expect(dialog.getByRole('button', { name: locale.dictate, exact: true })).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: locale.textAction, exact: true })).toHaveCount(0)
  const mic = dialog.getByRole('button', { name: locale.mic, exact: true })
  await mic.click()
  await expect(page.getByText(locale.recording, { exact: true })).toBeVisible()
  await expect(dialog.locator('#ai-rental-mode')).toHaveValue('holiday')
  await expect(draft).toHaveCount(0)
  await page.getByRole('button', { name: locale.cancel, exact: true }).click()
  await expect(mic).toBeEnabled()
  await page.evaluate(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('denied', 'NotAllowedError') } })
  await mic.click()
  await expect(page.getByRole('alert')).toHaveText(locale.denied)
  await expect(mic).toBeEnabled()
  expect(state.queries).toBe(0)
  expect(state.nativeCreates).toBe(0)
  expect(state.transcriptions).toBe(0)
})

test('Russian mobile menu keeps the field hidden until speech is recognized', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const state = await surface(page, false, 'ru')
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Искать голосом', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const mic = dialog.getByRole('button', { name: 'Записать запрос', exact: true })
  const draft = dialog.getByRole('textbox', { name: 'Текст записи' })
  await expect(mic).toBeEnabled()
  await expect(draft).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Вернуться к фильтрам' })).toHaveCount(0)
  await page.screenshot({ path: 'output/ai-home-voice-before.png' })
  state.failTranscription = true
  const record = async () => {
    await mic.click()
    await expect(dialog.getByText('Идёт запись…', { exact: true })).toBeVisible()
    await expect(draft).toHaveCount(0)
    await page.waitForTimeout(300)
    await dialog.getByRole('button', { name: 'Завершить запись', exact: true }).click()
  }
  await record()
  await expect(dialog.getByText('Не удалось распознать речь. Запишите запрос заново.')).toBeVisible()
  await expect(draft).toHaveCount(0)
  state.failTranscription = false
  state.transcript = 'Комната в Мадриде до 700 евро в месяц'
  await record()
  await expect(draft).toHaveValue(state.transcript)
  await expect(dialog.getByRole('button', { name: 'Поиск', exact: true })).toBeEnabled()
  await page.screenshot({ path: 'output/ai-home-voice-after.png' })
  expect(state.transcriptions).toBe(2)
  expect(state.queries).toBe(0)
  expect(state.nativeCreates).toBe(0)
})

test('microphone disconnect cancels capture and a new recording can be submitted', async ({ page }) => {
  const state = await surface(page, false, 'ru')
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await original(constraints)
      Object.assign(window, { latestVoiceTrack: stream.getAudioTracks()[0] })
      return stream
    }
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Искать голосом', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const mic = dialog.getByRole('button', { name: 'Записать запрос', exact: true })
  await mic.click()
  await expect(dialog.getByText('Идёт запись…', { exact: true })).toBeVisible()
  await page.evaluate(() => (window as Window & { latestVoiceTrack: MediaStreamTrack }).latestVoiceTrack.dispatchEvent(new Event('ended')))
  await expect(dialog.getByRole('alert')).toHaveText('Микрофон отключился. Подключите его и запишите запрос заново.')
  expect(state.transcriptions).toBe(0)
  await expect(mic).toBeEnabled()
  await mic.click()
  await expect(dialog.getByText('Идёт запись…', { exact: true })).toBeVisible()
  await page.waitForTimeout(300)
  await dialog.getByRole('button', { name: 'Завершить запись', exact: true }).click()
  const draft = dialog.getByRole('textbox', { name: 'Текст записи' })
  await expect(draft).toHaveValue(state.transcript)
  state.clarifyBudget = true
  await draft.fill('комната до 700 евро')
  await dialog.getByRole('button', { name: 'Поиск', exact: true }).click()
  await expect(dialog.getByText('Укажите, за какой период бюджет: за ночь, неделю или месяц.')).toBeVisible()
  await expect(draft).toHaveValue('комната до 700 евро')
  await expect(dialog.getByText('Осталось поисков на сегодня: 200')).toBeVisible()
  state.clarifyBudget = false
  await draft.fill('a room under 700 euros per month, unfurnished')
  await dialog.getByRole('button', { name: 'Поиск', exact: true }).click()
  await expect(dialog.getByText('Осталось поисков на сегодня: 199')).toBeVisible()
  expect(state.transcriptions).toBe(1)
  expect(state.queries).toBe(1)
})

test('session limit lets mobile users recover previous conditions without losing or sending the transcript', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 850 })
  const state = await surface(page, false, 'ru')
  state.sessionLimit = true
  state.transcript = 'найти квартиру до 700 евро в месяц на Tenerife.'
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Искать голосом', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Записать запрос', exact: true }).click()
  await expect(dialog.getByText('Идёт запись…', { exact: true })).toBeVisible()
  await page.waitForTimeout(300)
  await dialog.getByRole('button', { name: 'Завершить запись', exact: true }).click()
  const draft = dialog.getByRole('textbox', { name: 'Текст записи' })
  await expect(draft).toHaveValue(state.transcript)
  await dialog.getByRole('button', { name: 'Поиск', exact: true }).click()
  await dialog.getByRole('button', { name: 'Продолжить открытый диалог', exact: true }).click()
  await expect(dialog.getByText('Диалог восстановлен. Проверьте условия и нажмите кнопку поиска.')).toBeVisible()
  await expect(draft).toHaveValue(state.transcript)
  await expect(dialog.getByText('Условия для следующего сообщения', { exact: true })).toBeVisible()
  expect(state.nativeCreates).toBe(1)
  expect(state.recoveries).toBe(1)
  expect(state.queries).toBe(0)
})

test('Russian voice search retries a failed session start and keeps the apartment request', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 850 })
  const state = await surface(page, false, 'ru')
  state.transcript = 'Найти квартиру до 700 евро в месяц на Tenerife'
  state.apartmentRequest = true
  state.failNextCreate = true
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Искать голосом', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Записать запрос', exact: true }).click()
  await expect(dialog.getByText('Идёт запись…', { exact: true })).toBeVisible()
  await page.waitForTimeout(300)
  await dialog.getByRole('button', { name: 'Завершить запись', exact: true }).click()
  const draft = dialog.getByRole('textbox', { name: 'Текст записи' })
  await expect(draft).toHaveValue(state.transcript)
  const search = dialog.getByRole('button', { name: 'Поиск', exact: true })
  await search.click()
  await expect(dialog.getByText('Не удалось запустить поиск. Текст сохранён на экране. Нажмите «Поиск», чтобы повторить попытку.')).toBeVisible()
  await expect(draft).toHaveValue(state.transcript)
  expect(state.queries).toBe(0)
  await search.click()
  await expect(dialog.getByText('Остров Тенерифе', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByText('Отдельная квартира или студия', { exact: true }).first()).toBeVisible()
  await expect(dialog.getByText('Среди проверенных объявлений нет подходящих по всем условиям.', { exact: false })).toBeVisible()
  const nearby = dialog.getByRole('region', { name: 'Варианты чуть выше бюджета' })
  await expect(nearby.getByText('720 € в месяц · Сверх бюджета: +20 €')).toBeVisible()
  await expect(nearby.getByText('Test Tenerife studio')).toBeVisible()
  await expect(dialog.getByRole('region', { name: 'Подтверждённые результаты' }).getByText('Test Tenerife studio')).toHaveCount(0)
  expect(state.sessionCommands).toHaveLength(2)
  expect(state.sessionCommands[1]).toEqual(state.sessionCommands[0])
  expect(state.queries).toBe(1)
  expect(state.suggestionReads).toBe(1)
})

async function surface(page: Page, guestReturn = false, language = 'es') {
  await page.addInitScript(({ guestReturn, guestSid, guestRef, language }) => {
    localStorage.setItem('112233:language:v1', language)
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:has-session', '1')
    if (guestReturn) sessionStorage.setItem('112233:ai-continuation:v1:public-guest', JSON.stringify({ sessionId: guestSid, resultRef: guestRef }))
  }, { guestReturn, guestSid, guestRef, language })
  const state = { queries: 0, saves: 0, guestIssues: 0, nativeIssues: 0, nativeCreates: 0, nativeCapabilities: 0, nativeMapReads: 0, transcriptions: 0, failTranscription: false, clarifyBudget: false, transcript: 'a room under 700 euros per month', apartmentRequest: false, failNextCreate: false, sessionCommands: [] as unknown[], suggestionReads: 0, sessionLimit: false, recoveries: 0 }
  const intent = (guest = false) => ({ schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: guest ? guestSid : sid,
    version: guest ? 1 : state.queries, criteria: { rental_mode: { strength: 'hard', value: 'long' },
      ...(guest || state.queries ? { budget: { strength: 'hard', value: { amount: '700', currency: 'EUR', period: 'monthly' } }, furnished: { strength: 'hard', value: false } } : {}),
      ...(state.apartmentRequest && state.queries ? { geography: { strength: 'hard', value: { province_code: '38', island: 'tenerife' } }, accommodation: { strength: 'hard', value: { kind: 'apartment' } } } : {}) } })
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (url.hostname !== '127.0.0.1') return route.abort()
    if (path === '/api/v1/auth/refresh') return route.fulfill({ json: { accessToken: 'native-account-token', user } })
    if (path === '/api/v1/saved-searches/ai/capabilities') return route.fulfill({ json: { save: true } })
    if (path === '/api/v1/saved-searches/ai' && request.method() === 'POST') {
      expect(request.headers().authorization).toBe('Bearer native-account-token')
      expect(request.postDataJSON().token).toBe('in-memory-save-token')
      state.saves++; return route.fulfill({ json: { id: ref } })
    }
    const guest = path.startsWith('/ai-pilot/api/v1/ai-search/')
    if (guest || path.startsWith('/api/v1/ai-search/')) {
      expect(request.headers().authorization).toBe(guest ? undefined : 'Bearer native-account-token')
      const currentRef = guest ? guestRef : ref
      let value: unknown
      if (path.endsWith('/capabilities')) { if (!guest) state.nativeCapabilities++; value = { text: true, map: true, voice: true, saved_searches: false, save_handoff: true, budget_suggestions: state.apartmentRequest, session_recovery: state.sessionLimit } }
      else if (path.endsWith('/quota')) value = { limit: guest ? 3 : 200, remaining: guest ? 0 : 200 - state.queries }
      else if (path.endsWith('/identity')) { expect(guest).toBe(false); value = { ready: true } }
      else if (path.endsWith('/sessions')) {
        expect(guest).toBe(false)
        if (request.postDataJSON().recover_active) {
          state.recoveries++
          return route.fulfill({ json: { intent: intent(), expires_at: '2099-01-01T00:00:00Z' } })
        }
        state.nativeCreates++
        state.sessionCommands.push(request.postDataJSON())
        if (state.sessionLimit) return route.fulfill({ status: 429, json: { detail: 'SESSION_LIMIT' } })
        if (state.failNextCreate) {
          state.failNextCreate = false
          return route.fulfill({ status: 503, json: { detail: 'AI_SERVICE_UNAVAILABLE' } })
        }
        value = { intent: intent(), expires_at: '2099-01-01T00:00:00Z' }
      }
      else if (path.endsWith('/voice')) {
        expect(guest).toBe(false)
        const audio = request.postDataJSON()
        expect(audio.media_type).toBe('audio/wav')
        expect(audio.audio_base64.length).toBeGreaterThan(60)
        expect(audio.transcribe_only).toBe(true)
        state.transcriptions++
        if (state.failTranscription) return route.fulfill({ status: 422, json: { detail: 'ASR_FAILURE' } })
        value = { transcript: state.transcript }
      } else if (path.endsWith('/query')) {
        expect(guest).toBe(false)
        if (state.clarifyBudget) {
          expect(request.postDataJSON().text).toBe('комната до 700 евро')
          return route.fulfill({ json: { operation: { status: 'failed', remaining: 200, failure_code: 'CLARIFY_BUDGET_PERIOD', receipt: null },
            clarification: { reason: 'budget_period' }, cards: null } })
        }
        expect(request.postDataJSON().text).toBe(state.apartmentRequest ? state.transcript : 'a room under 700 euros per month, unfurnished')
        state.queries++
        value = { operation: { status: 'succeeded', remaining: 199, receipt: { result_ref: ref, count: 0 } }, cards: { cards: { items: [], total: 0, nextCursor: null, previousCursor: null }, intent_hash: 'native-hash' } }
      } else if (path.endsWith('/sessions/' + (guest ? guestSid : sid))) value = { intent: intent(guest), expires_at: '2099-01-01T00:00:00Z' }
      else if (path.endsWith('/results/' + currentRef)) value = { result_ref: currentRef, count: 0, intent_hash: 'native-hash', intent: intent(guest) }
      else if (path.endsWith('/cards')) {
        const items = []
        const budgetPrices = []
        if (request.postDataJSON().nearby_budget) {
          state.suggestionReads++
          const id = '00000000-0000-4000-8000-000000000041'
          items.push({ id, title: 'Test Tenerife studio', city: 'Adeje', area: '', approximateAddress: 'Adeje',
            rentalMode: 'long', price: 720, roomType: 'Estudio', currentResidents: 0, roomCapacity: 1,
            roomSizeM2: 30, availableFrom: null, billsIncluded: null, restrictions: [], isExternal: false,
            publishedAt: '2026-10-27', promoted: false, description: '', imageUrls: [] })
          budgetPrices.push({ listing_id: id, matched_amount: 720, matched_period: 'monthly',
            display_amount: 720, display_period: 'monthly', currency: 'EUR', confirmation: 'current_source_proof' })
        }
        value = { cards: { items, total: items.length, nextCursor: null, previousCursor: null }, budget_prices: budgetPrices, intent_hash: 'native-hash' }
      }
      else if (path.endsWith('/map')) { expect(guest).toBe(false); state.nativeMapReads++; value = { map: { items: [] }, intent_hash: 'native-hash' } }
      else if (path.endsWith('/save-token')) { if (guest) state.guestIssues++; else state.nativeIssues++; value = { token: 'in-memory-save-token', expires_in: 300 } }
      else throw Error('Unexpected AI request: ' + path)
      return route.fulfill({ json: value })
    }
    if (path.endsWith('/private-demo/status')) return route.fulfill({ json: { attempts: 30, maximum: 50, approved: false, halted: true, exhausted: false, catalog_ready: true, local_housing_available: true } })
    if (path.startsWith('/api/')) return route.fulfill({ status: 404, json: { detail: 'Not found' } })
    return route.continue()
  })
  return state
}

for (const width of [390, 1440]) for (const channel of ['stop', 'timer']) test(`native account ${width}px ${channel}: 200, owned replay and explicit save`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  const autoStop = channel === 'timer'
  if (autoStop) await page.clock.install()
  const state = await surface(page)
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Buscar con mi voz', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 200', { exact: true })).toBeVisible()
  const draft = page.locator('#ai-search-text')
  await expect(draft).toHaveCount(0)
  await page.getByRole('button', { name: 'Grabar búsqueda', exact: true }).click()
  await expect(page.getByText('Grabando…', { exact: true })).toBeVisible()
  await page.waitForTimeout(300)
  if (autoStop) await page.clock.fastForward(15000)
  else await page.getByRole('button', { name: 'Terminar grabación', exact: true }).click()
  await expect(draft).toHaveValue('a room under 700 euros per month')
  expect(state.transcriptions).toBe(1)
  expect(state.queries).toBe(0)
  expect(state.nativeCreates).toBe(0)
  await expect(page.getByText('Búsquedas disponibles hoy: 200', { exact: true })).toBeVisible()
  await draft.fill('a room under 700 euros per month, unfurnished')
  await page.getByRole('dialog').getByRole('button', { name: 'Buscar', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 199', { exact: true })).toBeVisible()
  await expect(page.getByText('700 EUR / mes', { exact: true }).first()).toBeVisible()
  if (!autoStop) {
    await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
    await expect.poll(() => state.nativeMapReads).toBeGreaterThan(0)
    expect(state.queries).toBe(1)
  }
  await page.reload()
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(1)
  await page.getByRole('button', { name: 'Buscar con mi voz', exact: true }).click()
  await expect(page.getByText('700 EUR / mes', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Guardar búsqueda y activar avisos', exact: true }).click()
  await expect.poll(() => state.saves).toBe(1)
  expect(state.queries).toBe(1); expect(state.nativeCreates).toBe(1); expect(state.nativeIssues).toBe(1); expect(state.guestIssues).toBe(0)
  const stored = await page.evaluate(() => JSON.stringify(Object.values(sessionStorage)))
  expect(stored).not.toContain('in-memory-save-token'); expect(stored).not.toContain('unfurnished'); expect(stored).not.toContain('audio_base64')
})

for (const width of [390, 1440]) test(`explicit guest return ${width}px stays read/save-only, then starts native scope`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  const state = await surface(page, true)
  await page.goto('/#/?ai=save')
  await expect(page.getByRole('button', { name: 'Guardar búsqueda y activar avisos', exact: true })).toBeVisible()
  await expect(page.locator('#ai-search-text')).toHaveCount(0)
  await page.getByRole('button', { name: 'Guardar búsqueda y activar avisos', exact: true }).click()
  await expect.poll(() => state.saves).toBe(1)
  expect(state.guestIssues).toBe(1); expect(state.nativeIssues).toBe(0); expect(state.queries).toBe(0)
  await page.getByRole('button', { name: 'Iniciar nueva conversación', exact: true }).click()
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Buscar con mi voz', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 200', { exact: true })).toBeVisible()
  await expect(page.getByText('700 EUR / mes', { exact: true })).toHaveCount(0)
  expect(state.queries).toBe(0); expect(state.nativeCreates).toBe(0)
  expect(await page.evaluate(() => sessionStorage.getItem('112233:ai-continuation:v1:public-guest'))).toContain(guestRef)
})

test('an old 401 refresh cannot overwrite a new login or retry its account request', async ({ page }) => {
  const state = await surface(page)
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  let refreshSeen = false, reads = 0, release = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/auth/refresh', async route => {
    refreshSeen = true; await gate
    await route.fulfill({ json: { accessToken: 'expired-account-refresh-token', user } })
  })
  await page.route('**/api/v1/ai-search/quota', route => {
    reads++
    if (reads === 1) return route.fulfill({ status: 401, json: { detail: 'Expired access token' } })
    expect(route.request().headers().authorization).toBe('Bearer other-account-token')
    return route.fulfill({ json: { remaining: 200 } })
  })
  const previous = page.evaluate(async () => {
    const path = '/src/api/client.ts', client = await import(path)
    try { await client.api('/ai-search/quota', { aiAuthority: 'registered' }); return 200 } catch (error) { return (error as { status: number }).status }
  })
  await expect.poll(() => refreshSeen).toBe(true)
  await page.evaluate(async () => { const path = '/src/api/client.ts'; (await import(path)).setAccessToken('other-account-token') })
  release()
  expect(await previous).toBe(401)
  expect(reads).toBe(1)
  expect(await page.evaluate(async () => { const path = '/src/api/client.ts'; return (await (await import(path)).api('/ai-search/quota', { aiAuthority: 'registered' })).remaining })).toBe(200)
  expect(reads).toBe(2)
})

test('logout invalidates native authority immediately and its delayed reply preserves a later login', async ({ page }) => {
  const state = await surface(page)
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  let logoutSeen = false, release = () => {}, reads = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/auth/logout', async route => { logoutSeen = true; await gate; await route.fulfill({ status: 204 }) })
  await page.route('**/api/v1/ai-search/quota', route => {
    reads++; expect(route.request().headers().authorization).toBe('Bearer other-account-token')
    return route.fulfill({ json: { remaining: 200 } })
  })
  const logout = page.evaluate(async () => { const path = '/src/api/auth.ts'; await (await import(path)).logoutSession() })
  await expect.poll(() => logoutSeen).toBe(true)
  expect(await page.evaluate(async () => {
    const path = '/src/api/client.ts', client = await import(path)
    try { await client.api('/ai-search/quota', { aiAuthority: 'registered' }); return 200 } catch (error) { return (error as { status: number }).status }
  })).toBe(401)
  expect(reads).toBe(0)
  await page.evaluate(async () => { const path = '/src/api/client.ts'; (await import(path)).setAccessToken('other-account-token') })
  release(); await logout
  expect(await page.evaluate(async () => { const path = '/src/api/client.ts'; return (await (await import(path)).api('/ai-search/quota', { aiAuthority: 'registered' })).remaining })).toBe(200)
  expect(reads).toBe(1)
})

test('a new login waits for cookie revocation so its refresh cookie survives', async ({ page }) => {
  const state = await surface(page)
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  let logoutSeen = false, logoutReturned = false, logins = 0, release = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/auth/logout', async route => {
    logoutSeen = true; await gate; logoutReturned = true
    await route.fulfill({ status: 204, headers: { 'Set-Cookie': 'refresh_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax' } })
  })
  await page.route('**/api/v1/auth/login', async route => {
    logins++; expect(logoutReturned).toBe(true)
    expect(route.request().headers().authorization).toBeUndefined()
    await route.fulfill({ json: { accessToken: 'new-account-token', user: { ...user, id: ref } },
      headers: { 'Set-Cookie': 'refresh_token=new-account; Path=/; HttpOnly; SameSite=Lax' } })
  })
  const change = page.evaluate(async () => {
    const path = '/src/api/auth.ts', auth = await import(path)
    const logout = auth.logoutSession()
    const login = auth.loginWithPassword('another@example.test', 'not-a-real-password')
    const [, account] = await Promise.all([logout, login])
    return account.id
  })
  await expect.poll(() => logoutSeen).toBe(true)
  expect(logins).toBe(0)
  release(); expect(await change).toBe(ref)
  expect(logins).toBe(1)
  expect((await page.context().cookies()).find(cookie => cookie.name === 'refresh_token')?.value).toBe('new-account')
})
