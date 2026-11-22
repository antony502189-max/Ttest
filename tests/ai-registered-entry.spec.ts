import { expect, test, type Page } from '@playwright/test'

const userId = '00000000-0000-4000-8000-000000000011'
const sid = '00000000-0000-4000-8000-000000000021', ref = '00000000-0000-4000-8000-000000000022'
const guestSid = '00000000-0000-4000-8000-000000000031', guestRef = '00000000-0000-4000-8000-000000000032'
const user = { id: userId, name: 'Native Account', email: 'synthetic@example.test', role: 'tenant', initials: 'NA', phone: '', whatsapp: '', telegram: '', about: '', showPhone: false, showWhatsApp: false, emailVerified: true }

for (const locale of [
  { language: 'es', open: 'También puedes escribir tu búsqueda', mic: 'Dictar búsqueda', recording: 'Grabando…', cancel: 'Cancelar grabación', denied: 'Permite el acceso al micrófono en el navegador o escribe tu búsqueda.', guide: 'Qué puedes indicar', useExample: 'Usar este ejemplo', close: 'Cerrar', nightly: 'Estudio en Madrid hasta 70 euros por noche, amueblado' },
  { language: 'ru', open: 'Также можно написать запрос', mic: 'Надиктовать запрос', recording: 'Идёт запись…', cancel: 'Отменить запись', denied: 'Разрешите доступ к микрофону в браузере или введите запрос текстом.', guide: 'Что можно указать', useExample: 'Подставить пример', close: 'Закрыть', nightly: 'Студия в Мадриде до 70 евро за ночь, с мебелью' },
  { language: 'en', open: 'You can also type your search', mic: 'Dictate search', recording: 'Recording…', cancel: 'Cancel recording', denied: 'Allow microphone access in your browser or type your search.', guide: 'What you can include', useExample: 'Use this example', close: 'Close', nightly: 'A studio in Madrid under 70 euros per night, furnished' },
]) test(`native search ${locale.language}: mobile guidance, examples and microphone recovery without a query`, async ({ page }) => {
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
  await guide.getByRole('button', { name: locale.useExample, exact: true }).click()
  const draft = dialog.locator('#ai-search-text')
  await expect(draft).toHaveValue(locale.nightly)
  await expect(draft).toBeFocused()
  expect(await dialog.evaluate(node => node.scrollWidth)).toBe(await dialog.evaluate(node => node.clientWidth))
  const mic = page.getByRole('button', { name: locale.mic, exact: true })
  await mic.click()
  await expect(page.getByText(locale.recording, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: locale.cancel, exact: true }).click()
  await expect(mic).toBeEnabled()
  await page.evaluate(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('denied', 'NotAllowedError') } })
  await mic.click()
  await expect(page.getByRole('alert')).toHaveText(locale.denied)
  await expect(mic).toBeEnabled()
  expect(state.queries).toBe(0)
  expect(state.nativeCreates).toBe(0)
})

async function surface(page: Page, guestReturn = false, language = 'es') {
  await page.addInitScript(({ guestReturn, guestSid, guestRef, language }) => {
    localStorage.setItem('112233:language:v1', language)
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:has-session', '1')
    if (guestReturn) sessionStorage.setItem('112233:ai-continuation:v1:public-guest', JSON.stringify({ sessionId: guestSid, resultRef: guestRef }))
  }, { guestReturn, guestSid, guestRef, language })
  const state = { queries: 0, saves: 0, guestIssues: 0, nativeIssues: 0, nativeCreates: 0, nativeCapabilities: 0, nativeMapReads: 0 }
  const intent = (guest = false) => ({ schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: guest ? guestSid : sid,
    version: guest ? 1 : state.queries, criteria: { rental_mode: { strength: 'hard', value: 'long' },
      ...(guest || state.queries ? { budget: { strength: 'hard', value: { amount: '700', currency: 'EUR', period: 'monthly' } }, furnished: { strength: 'hard', value: false } } : {}) } })
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
      if (path.endsWith('/capabilities')) { if (!guest) state.nativeCapabilities++; value = { text: true, map: true, voice: true, saved_searches: false, save_handoff: true } }
      else if (path.endsWith('/quota')) value = { limit: guest ? 3 : 200, remaining: guest ? 0 : 200 - state.queries }
      else if (path.endsWith('/identity')) { expect(guest).toBe(false); value = { ready: true } }
      else if (path.endsWith('/sessions')) { expect(guest).toBe(false); state.nativeCreates++; value = { intent: intent(), expires_at: '2099-01-01T00:00:00Z' } }
      else if (path.endsWith('/query') || path.endsWith('/voice')) {
        expect(guest).toBe(false)
        if (path.endsWith('/voice')) { expect(request.postDataJSON().media_type).toBe('audio/wav'); expect(request.postDataJSON().audio_base64.length).toBeGreaterThan(60) }
        else expect(request.postDataJSON().text).toBe('a room under 700 euros per month, unfurnished')
        state.queries++
        value = { operation: { status: 'succeeded', remaining: 199, receipt: { result_ref: ref, count: 0 } }, cards: { cards: { items: [], total: 0, nextCursor: null, previousCursor: null }, intent_hash: 'native-hash' } }
      } else if (path.endsWith('/sessions/' + (guest ? guestSid : sid))) value = { intent: intent(guest), expires_at: '2099-01-01T00:00:00Z' }
      else if (path.endsWith('/results/' + currentRef)) value = { result_ref: currentRef, count: 0, intent_hash: 'native-hash', intent: intent(guest) }
      else if (path.endsWith('/cards')) value = { cards: { items: [], total: 0, nextCursor: null, previousCursor: null }, intent_hash: 'native-hash' }
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

for (const width of [390, 1440]) for (const channel of ['text', 'voice']) test(`native account ${width}px ${channel}: 200, owned replay and explicit save`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  const state = await surface(page)
  await page.goto('/#/')
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'También puedes escribir tu búsqueda', exact: true }).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 200', { exact: true })).toBeVisible()
  if (channel === 'text') {
    await page.locator('#ai-search-text').fill('a room under 700 euros per month, unfurnished')
    await page.getByRole('button', { name: 'Buscar vivienda', exact: true }).click()
  } else {
    await page.getByRole('button', { name: 'Dictar búsqueda', exact: true }).click()
    await expect(page.getByText('Grabando…', { exact: true })).toBeVisible()
    await page.waitForTimeout(300)
    await page.getByRole('button', { name: 'Detener y buscar', exact: true }).click()
  }
  await expect(page.getByText('Búsquedas disponibles hoy: 199', { exact: true })).toBeVisible()
  await expect(page.getByText('700 EUR / mes', { exact: true }).first()).toBeVisible()
  if (channel === 'text') {
    await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
    await expect.poll(() => state.nativeMapReads).toBeGreaterThan(0)
    expect(state.queries).toBe(1)
  }
  await page.reload()
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(1)
  await page.getByRole('button', { name: 'También puedes escribir tu búsqueda', exact: true }).click()
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
  await expect(page.locator('#ai-search-text')).toBeDisabled()
  await page.getByRole('button', { name: 'Guardar búsqueda y activar avisos', exact: true }).click()
  await expect.poll(() => state.saves).toBe(1)
  expect(state.guestIssues).toBe(1); expect(state.nativeIssues).toBe(0); expect(state.queries).toBe(0)
  await page.getByRole('button', { name: 'Iniciar nueva conversación', exact: true }).click()
  await expect.poll(() => state.nativeCapabilities).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'También puedes escribir tu búsqueda', exact: true }).click()
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
