// Functional acceptance against real HTTPS UI/API/PostGIS/Redis. No API fixtures.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, request, expect } from '@playwright/test'
import { labControl as control } from './ai-text-lab-control.mjs'

const origin = 'https://localhost:9443'
const dir = new URL('../output/ai-text-acceptance/', import.meta.url)
await mkdir(dir, { recursive: true })
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const headers = { Origin: origin, 'X-AI-Request': '1' }
const report = { source, origin, apiMocks: false, model: 'finite synthetic parser only', cases: [], externalRequests: [], pageErrors: [], backpressure: [] }
const record = (name, details = {}) => { report.cases.push({ name, ...details, passed: true }); console.log('PASS ' + name) }
const fixture = (await control({ action: 'seed' })).ids
const all = Object.values(fixture).sort(), dog = ['a', 'b', 'c', 'f', 'g'].map(n => fixture[n]).sort()
const budget = ['a', 'b', 'c'].map(n => fixture[n]).sort()
const ids = items => items.map(item => item.id).sort()
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const browser = await chromium.launch()
const contexts = [], sessions = new Set()
async function openAI(page) {
  // Mobile product intentionally replays its onboarding on reload. Complete
  // that real flow instead of treating the landing screen as an AI failure.
  for (let i = 0; i < 3; i++) {
    const next = page.locator('.m2-onboarding .m2-primary')
    if (!await next.count()) break
    await next.click()
  }
  const skip = page.locator('.m2-auth-skip')
  if (await skip.count()) await skip.click()
  await page.locator('.home-ai-search__action').click()
}
async function json(response, status = 200) {
  assert.equal(response.status(), status, await response.text())
  return response.json()
}
async function call(client, method, path, data, extra = {}) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const response = await client.fetch(origin + path, { method, headers: { ...headers, ...extra }, data })
    if (response.status() !== 429) return response
    const body = await response.json()
    if (!['ATTEMPT_LIMIT', 'SESSION_LIMIT'].includes(body.detail)) return response
    const seconds = Math.min(60, Math.max(1, Number(response.headers()['retry-after']) || 1))
    report.backpressure.push({ path, code: body.detail, waitSeconds: seconds })
    console.log(`Waiting for existing technical gate: ${seconds}s`)
    await sleep(seconds * 1000 + 100)
  }
  throw Error('technical gate did not recover')
}
async function guest(language = 'es', width = 1280) {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width, height: 1100 } })
  contexts.push(ctx)
  await json(await call(ctx.request, 'POST', '/api/v1/ai-search/identity'))
  const page = await ctx.newPage()
  page.on('request', r => { if (new URL(r.url()).origin !== origin) report.externalRequests.push(r.url()) })
  page.on('pageerror', e => report.pageErrors.push(e.message))
  await page.addInitScript(lang => {
    localStorage.setItem('112233:language:v1', lang)
    localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
  }, language)
  await page.goto(origin, { waitUntil: 'networkidle' })
  await openAI(page)
  await expect(page.locator('#ai-rental-mode')).toBeEnabled()
  await page.locator('#ai-rental-mode').selectOption('none')
  return { ctx, page }
}
async function submit(page, text, expectedIds) {
  await expect(page.locator('#ai-search-text')).toBeEnabled()
  await page.locator('#ai-search-text').fill(text)
  const wait = page.waitForResponse(r => r.url() === origin + '/api/v1/ai-search/query')
  await page.locator('.ai-search-dialog > .home-ai-search__action').click()
  let response = await wait
  for (let attempt = 0; response.status() === 429 && attempt < 3; attempt++) {
    const body = await response.json()
    if (body.detail !== 'ATTEMPT_LIMIT') break
    const seconds = Math.min(60, Math.max(1, Number(response.headers()['retry-after']) || 1))
    report.backpressure.push({ phase: 'browser-query', waitSeconds: seconds })
    await sleep(seconds * 1000 + 100)
    const retry = page.waitForResponse(r => r.url() === origin + '/api/v1/ai-search/query')
    await page.locator('.ai-search-dialog > .home-ai-search__action').click()
    response = await retry
  }
  const answer = await json(response)
  assert.equal(answer.operation.status, 'succeeded', JSON.stringify(answer))
  assert.equal(answer.cards.cards.total, expectedIds.length)
  // UI requests six per page; total IDs are independently checked by reads.
  assert.ok(ids(answer.cards.cards.items).every(id => expectedIds.includes(id)))
  sessions.add(response.request().postDataJSON().session_id)
  await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(Math.min(6, expectedIds.length))
  return { answer, body: response.request().postDataJSON() }
}
async function owned(client, rental_mode = 'holiday', auth = {}) {
  const result = await json(await call(client, 'POST', '/api/v1/ai-search/sessions', { idempotency_key: crypto.randomUUID(), rental_mode }, auth))
  sessions.add(result.intent.session_id)
  return result.intent
}
async function query(client, intent, text, auth = {}, limit = 1) {
  const body = { idempotency_key: crypto.randomUUID(), session_id: intent.session_id, expected_version: intent.version, text, search: { limit } }
  const answer = await json(await call(client, 'POST', '/api/v1/ai-search/query', body, auth))
  assert.equal(answer.operation.status, 'succeeded', JSON.stringify(answer))
  intent.version++
  return { answer, body }
}
try {
  const probe = await request.newContext({ ignoreHTTPSErrors: true })
  assert.equal((await json(await probe.get(origin + '/build-info.json'))).source, source)
  await probe.dispose()
  // Actual UI on every supported language and representative viewport.
  for (const language of ['es', 'en', 'ru']) for (const width of [320, 768, 1440]) {
    const { ctx, page } = await guest(language, width)
    const first = await submit(page, 'туризм', all)
    const dialog = page.getByRole('dialog')
    assert.ok(await dialog.evaluate(e => e.scrollWidth <= e.clientWidth + 1))
    const next = page.locator('.ai-search-dialog nav button').last()
    await expect(next).toBeEnabled()
    await next.click()
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(1)
    const lastIds = await page.locator('.ai-search-dialog__cards [data-listing-id]').evaluateAll(nodes => nodes.map(n => n.dataset.listingId))
    assert.deepEqual([...ids(first.answer.cards.cards.items), ...lastIds].sort(), all)
    await page.locator('.ai-search-dialog nav button').first().click()
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(6)
    assert.deepEqual(await page.locator('.ai-search-dialog__cards [data-listing-id]').evaluateAll(nodes => nodes.map(n => n.dataset.listingId).sort()), ids(first.answer.cards.cards.items))
    const followed = await submit(page, 'с маленькой собакой', dog)
    const ref = followed.answer.operation.receipt.result_ref
    const meta = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/results/' + ref))
    assert.equal(meta.intent.criteria.pets.strength, 'hard')
    await page.reload({ waitUntil: 'networkidle' })
    await openAI(page)
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(5)
    await expect(page.locator('#ai-rental-mode')).toHaveValue('keep')
    // Restored session is current, committed result conditions remain bound.
    const third = await submit(page, 'до 60 евро за ночь', budget)
    const result = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/results/' + third.answer.operation.receipt.result_ref))
    assert.equal(result.intent.version, 3)
    assert.equal(result.intent.criteria.budget.value.period, 'nightly')
    const mapButton = page.locator('section[aria-busy] > button[aria-pressed]')
    await mapButton.click()
    await expect(page.getByText('Маркеров: 3', { exact: true })).toBeVisible()
    const storage = await page.evaluate(() => ({ ...localStorage, ...sessionStorage }))
    assert.ok(!JSON.stringify(storage).includes('до 60 евро за ночь'))
    const locator = Object.entries(storage).find(([key]) => key.startsWith('112233:ai-continuation:'))?.[1]
    assert.deepEqual(Object.keys(JSON.parse(locator)).sort(), ['resultRef', 'sessionId'])
    await page.getByRole('region', { name: 'Локальная координатная карта' }).screenshot({ path: fileURLToPath(new URL(`${language}-${width}-map.png`, dir)) })
    const quota = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/quota'))
    assert.equal(quota.used, 3); assert.equal(quota.reserved, 0)
    record(`UI ${language} ${width}px: paging, follow-up, reload, conditions, map, privacy, quota`, { count: 3, first: first.answer.cards.cards.total })
    await control({ action: 'expire', session_id: third.body.session_id })
    await ctx.close()
    await sleep(2000)
  }
  // One authenticated client for non-UI semantic and live-mutation matrix.
  const api = await request.newContext({ ignoreHTTPSErrors: true })
  await json(await call(api, 'POST', '/api/v1/ai-search/identity'))
  const login = await json(await call(api, 'POST', '/api/v1/auth/login', { email: 'acceptance-user@synthetic.example', password: 'Synthetic-Lab-Only-2026!' }))
  const auth = { Authorization: 'Bearer ' + login.accessToken }
  const intent = await owned(api, 'holiday', auth)
  let q = await query(api, intent, 'все варианты', auth)
  assert.equal(q.answer.cards.cards.total, 7)
  q = await query(api, intent, 'желательно с балконом', auth)
  assert.equal(q.answer.cards.cards.total, 7)
  q = await query(api, intent, 'обязательно с балконом', auth)
  assert.equal(q.answer.cards.cards.total, 4)
  q = await query(api, intent, 'с маленькой собакой', auth)
  assert.equal(q.answer.cards.cards.total, 3)
  q = await query(api, intent, 'до 40 евро за ночь', auth)
  assert.equal(q.answer.cards.cards.total, 0)
  record('hard/soft, explicit deny, unknown facts, intersecting hard criteria and zero result')
  await control({ action: 'expire', session_id: intent.session_id })
  const live = await owned(api, 'holiday', auth)
  const base = await query(api, live, 'все варианты', auth)
  const ref = base.answer.operation.receipt.result_ref
  const bounds = { north: 28.2, south: 28.05, west: -16.8, east: -16.65, zoom: 14 }
  for (const kind of ['source', 'moderation', 'price', 'hidden']) {
    const before = await json(await call(api, 'POST', `/api/v1/ai-search/results/${ref}/cards`, { search: { limit: 1 } }, auth))
    await control({ action: 'change', name: 'g', kind })
    try {
      const next = await call(api, 'POST', `/api/v1/ai-search/results/${ref}/cards`, { search: { limit: 1, cursor: before.cards.nextCursor } }, auth)
      if (next.status() === 409) assert.equal((await next.json()).detail, 'AI_REQUERY_REQUIRED')
      else {
        const livePage = await json(next)
        assert.equal(livePage.cards.total, 6); assert.ok(!ids(livePage.cards.items).includes(fixture.g))
      }
      const page = await json(await call(api, 'POST', `/api/v1/ai-search/results/${ref}/cards`, { search: { limit: 50 } }, auth))
      const map = await json(await call(api, 'POST', `/api/v1/ai-search/results/${ref}/map`, { search: bounds }, auth))
      assert.equal(page.cards.total, 6); assert.ok(!ids(page.cards.items).includes(fixture.g))
      assert.equal(map.map.items.length, 6); assert.ok(!ids(map.map.items).includes(fixture.g))
      if (kind === 'price') assert.equal((await control({ action: 'change', name: 'g', kind: 'proof' })).prepared, false)
      record(`live ${kind} change between pages: excluded before count, cards and map`)
    } finally { await control({ action: 'change', name: 'g', kind: 'restore' }) }
  }
  // Read the real old committed result while editable session has newer criteria.
  const narrow = await query(api, live, 'с маленькой собакой', auth)
  const old = await json(await call(api, 'POST', `/api/v1/ai-search/results/${ref}/cards`, { search: { limit: 50 } }, auth))
  assert.equal(old.cards.total, 7); assert.equal(narrow.answer.cards.cards.total, 5)
  record('committed result remains distinct from newer editable session')
  await control({ action: 'expire', session_id: live.session_id })
  await json(await call(api, 'POST', `/api/v1/ai-search/results/${ref}/cards`, { search: {} }, auth), 409)
  record('expired session/result cannot page or silently regain access')
  await api.dispose()
  {
    const { ctx, page } = await guest()
    const guestResult = await submit(page, 'туризм', all)
    await page.goto(origin + '/#/acceso')
    await page.getByRole('button', { name: 'Iniciar sesión con email', exact: true }).click()
    await page.getByLabel('Email', { exact: true }).fill('acceptance-user@synthetic.example')
    await page.getByLabel('Contraseña', { exact: true }).fill('Synthetic-Lab-Only-2026!')
    const logged = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'))
    await page.locator('form button[type=submit]').click()
    const identity = await json(await logged)
    await page.waitForURL(origin + '/#/')
    await openAI(page)
    await expect(page.locator('.ai-search-dialog__cards')).toHaveCount(0)
    await page.locator('#ai-rental-mode').selectOption('none')
    const authResult = await submit(page, 'туризм', all)
    const authHeaders = { Authorization: 'Bearer ' + identity.accessToken }
    const before = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/quota', undefined, authHeaders))
    assert.equal(before.limit, 200)
    await json(await call(ctx.request, 'GET', '/api/v1/ai-search/sessions/' + guestResult.body.session_id, undefined, authHeaders), 404)
    await json(await call(ctx.request, 'GET', '/api/v1/ai-search/sessions/' + authResult.body.session_id), 404)
    const refreshed = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/refresh'))
    await page.reload({ waitUntil: 'networkidle' })
    const refreshedIdentity = await json(await refreshed)
    await openAI(page)
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(6)
    const after = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/quota', undefined,
      { Authorization: 'Bearer ' + refreshedIdentity.accessToken }))
    assert.equal(after.used, before.used)
    record('real browser login and refresh: auth reload, 200/day, guest/auth ownership separation')
    await ctx.close()
  }
  {
    const { ctx, page } = await guest('es', 320)
    await submit(page, 'туризм', all)
    const hard = ['a', 'b', 'd', 'f'].map(n => fixture[n])
    await submit(page, 'обязательно с балконом', hard)
    await submit(page, 'до 40 евро за ночь', [])
    await expect(page.getByText('No encontramos opciones con todas las condiciones confirmadas.', { exact: false })).toBeVisible()
    record('real mobile UI zero-result and hard unknown exclusion')
    await ctx.close()
  }
  {
    const { ctx, page } = await guest()
    const found = await submit(page, 'туризм', all)
    const sid = found.body.session_id, ref = found.answer.operation.receipt.result_ref
    const raw = await page.evaluate(() => sessionStorage.getItem('112233:ai-continuation:v1:guest'))
    let dropped = false
    await page.route('**/api/v1/ai-search/sessions/*', async route => {
      if (!dropped && route.request().method() === 'GET') {
        dropped = true; await route.fetch(); await route.abort('failed')
      } else await route.continue()
    })
    await page.reload({ waitUntil: 'networkidle' })
    await openAI(page)
    await expect(page.getByRole('button', { name: 'Reintentar sincronización', exact: true })).toBeVisible()
    assert.equal(await page.evaluate(() => sessionStorage.getItem('112233:ai-continuation:v1:guest')), raw)
    await page.getByRole('button', { name: 'Reintentar sincronización', exact: true }).click()
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(6)
    record('reload acknowledgement loss retains locator; explicit retry restores real cards')
    const foreign = await guest()
    await foreign.page.evaluate(value => sessionStorage.setItem('112233:ai-continuation:v1:guest', value), raw)
    await foreign.page.reload({ waitUntil: 'networkidle' })
    await openAI(foreign.page)
    await expect(foreign.page.locator('#ai-rental-mode')).toBeEnabled()
    await expect(foreign.page.locator('.ai-search-dialog__cards')).toHaveCount(0)
    assert.equal((await json(await call(foreign.ctx.request, 'GET', '/api/v1/ai-search/quota'))).used, 0)
    record('foreign guest storage locators grant no session or result authority')
    await foreign.ctx.close()
    await control({ action: 'change', name: 'a', kind: 'missing' })
    try {
      await page.locator('.ai-search-dialog nav button').last().click()
      await expect(page.getByText('Los resultados ya no están disponibles.', { exact: false })).toBeVisible()
      await expect(page.locator('.ai-search-dialog__cards')).toHaveCount(0)
      await expect(page.locator('.ai-search-dialog nav button').last()).toBeDisabled()
      record('missing proof invalidates cursor; stale visible cards are removed, editable session remains')
    } finally { await control({ action: 'change', name: 'a', kind: 'restore' }) }
    await control({ action: 'expire', session_id: sid })
    await page.reload({ waitUntil: 'networkidle' })
    await openAI(page)
    await expect(page.locator('#ai-rental-mode')).toBeEnabled()
    await expect(page.locator('.ai-search-dialog__cards')).toHaveCount(0)
    const expired = await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', found.body))
    assert.equal(expired.replay, true); assert.equal(expired.operation.used, 1)
    assert.equal(expired.cards, null); assert.equal(expired.cards_error, 'RESULT_EXPIRED_REQUERY_REQUIRED')
    await json(await call(ctx.request, 'GET', '/api/v1/ai-search/results/' + ref), 409)
    record('expiry across reload clears presentation; old receipt replay never debits again')
    await ctx.close()
  }
  {
    const { ctx, page } = await guest()
    const intent = await owned(ctx.request)
    const body = { idempotency_key: crypto.randomUUID(), session_id: intent.session_id, expected_version: 0,
      text: 'все варианты', search: { limit: 1 } }
    await control({ action: 'arm', session_id: intent.session_id, version: 0, fault: 'delay' })
    const first = call(ctx.request, 'POST', '/api/v1/ai-search/query', body)
    // Await actual parser entry, rather than inferring it from elapsed time.
    for (let i = 0; i < 20; i++) {
      if ((await control({ action: 'inspect', session_id: intent.session_id, version: 0 })).calls) break
      await sleep(100)
    }
    const second = await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', body))
    assert.ok(['running', 'succeeded'].includes(second.operation.status))
    const completed = await json(await first)
    const repeated = await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', body))
    assert.equal(completed.operation.status, 'succeeded'); assert.equal(repeated.replay, true)
    assert.equal(repeated.operation.used, 1)
    await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', { ...body, text: 'туризм' }), 409)
    const observed = await control({ action: 'inspect', session_id: intent.session_id, version: 0 })
    assert.equal(observed.calls, 1); assert.equal(observed.requests.length, 1)
    const conflict = await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', { ...body, idempotency_key: crypto.randomUUID() }))
    assert.equal(conflict.operation.status, 'failed'); assert.equal(conflict.operation.failure_code, 'SESSION_VERSION_CONFLICT')
    assert.equal((await control({ action: 'inspect', session_id: intent.session_id, version: 0 })).calls, 1)
    record('concurrent duplicate, terminal replay, payload conflict and stale version: one parser call, one debit')
    await ctx.close()
  }
  // Lost replies are network faults after route.fetch completed on the REAL API.
  for (const phase of ['query', 'sessions', 'reset']) {
    const { ctx, page } = await guest()
    let body, committed, intercepted = false
    if (phase === 'reset') await submit(page, 'туризм', all)
    const suffix = phase === 'reset' ? '/reset' : '/' + phase
    await page.route('**/api/v1/ai-search/**', async route => {
      if (!intercepted && route.request().method() === 'POST' && new URL(route.request().url()).pathname.endsWith(suffix)) {
        intercepted = true; body = route.request().postDataJSON()
        const response = await route.fetch()
        assert.equal(response.status(), 200)
        committed = await response.json()
        await route.abort('failed')
      } else await route.continue()
    })
    if (phase === 'reset') {
      await page.getByRole('button', { name: 'Iniciar nueva conversación', exact: true }).click()
      await expect(page.getByRole('status').filter({ hasText: 'No se pudo iniciar' })).toBeVisible()
      await page.getByRole('button', { name: 'Iniciar nueva conversación', exact: true }).click()
      assert.ok(committed.intent.session_id)
      await expect.poll(async () => page.evaluate(() => JSON.parse(sessionStorage.getItem('112233:ai-continuation:v1:guest') || 'null')?.sessionId))
        .toBe(committed.intent.session_id)
    } else {
      await page.locator('#ai-search-text').fill('туризм')
      await page.locator('.ai-search-dialog > .home-ai-search__action').click()
      await expect(page.getByRole('status').filter({ hasText: 'No se pudo' })).toBeVisible()
      const retried = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(suffix))
      await page.locator('.ai-search-dialog > .home-ai-search__action').click()
      assert.deepEqual((await retried).request().postDataJSON(), body)
      await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(6)
      if (phase === 'sessions') {
        const saved = await page.evaluate(() => JSON.parse(sessionStorage.getItem('112233:ai-continuation:v1:guest')))
        assert.equal(saved.sessionId, committed.intent.session_id)
      }
      if (phase === 'query') {
        const inspect = await control({ action: 'inspect', session_id: body.session_id, version: body.expected_version })
        assert.equal(inspect.calls, 1); assert.equal(inspect.requests.length, 1)
        assert.equal(inspect.requests[0].result_ref, committed.operation.receipt.result_ref)
        assert.equal((await json(await call(ctx.request, 'GET', '/api/v1/ai-search/quota'))).used, 1)
      }
    }
    record(`lost ${phase} acknowledgement: actual backend commit, exact retry, no duplicate effect`)
    await ctx.close()
  }
  for (const fault of ['failure', 'cancel', 'delay']) {
    const { ctx, page } = await guest()
    const state = await owned(ctx.request)
    // Persist only the locator so the UI obtains the owned server session.
    await page.evaluate(sid => sessionStorage.setItem('112233:ai-continuation:v1:guest', JSON.stringify({ sessionId: sid })), state.session_id)
    await page.reload({ waitUntil: 'networkidle' })
    await openAI(page)
    await expect(page.locator('#ai-rental-mode')).toHaveValue('keep')
    await control({ action: 'arm', session_id: state.session_id, version: 0, fault })
    await page.locator('#ai-search-text').fill('все варианты')
    const sent = page.waitForRequest(r => r.url().endsWith('/ai-search/query'))
    await page.locator('.ai-search-dialog > .home-ai-search__action').click()
    const body = (await sent).postDataJSON()
    if (fault === 'delay') {
      await page.getByRole('button', { name: 'Dejar de esperar', exact: true }).click()
      await expect(page.locator('.ai-search-dialog > .home-ai-search__action')).toHaveText('Comprobar el mismo intento')
      await sleep(3300)
    } else if (fault === 'failure') {
      await expect(page.locator('#ai-search-text')).toBeEnabled()
    } else {
      await expect(page.locator('.ai-search-dialog > .home-ai-search__action')).toHaveText('Comprobar el mismo intento')
    }
    if (fault !== 'failure') {
      const checked = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
      await page.locator('.ai-search-dialog > .home-ai-search__action').click()
      const terminal = await checked
      assert.deepEqual(terminal.request().postDataJSON(), body)
      assert.equal((await json(terminal)).operation.status, fault === 'delay' ? 'succeeded' : 'failed')
      await expect(page.locator('#ai-search-text')).toBeEnabled()
    }
    const replay = await json(await call(ctx.request, 'POST', '/api/v1/ai-search/query', body))
    const observed = await control({ action: 'inspect', session_id: state.session_id, version: 0 })
    assert.equal(observed.calls, 1)
    assert.equal(observed.requests.length, 1)
    const quota = await json(await call(ctx.request, 'GET', '/api/v1/ai-search/quota'))
    if (fault === 'delay') { assert.equal(replay.operation.status, 'succeeded'); assert.equal(quota.used, 1) }
    else { assert.equal(replay.operation.status, 'failed'); assert.equal(quota.used, 0) }
    assert.equal(quota.reserved, 0)
    record(`parser ${fault}: real lifecycle + retry once, bounded quota semantics`)
    await ctx.close()
  }
  assert.deepEqual(report.externalRequests, [])
  assert.deepEqual(report.pageErrors, [])
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'; report.failure = String(error.stack || error)
  report.pages = []
  for (const ctx of contexts) for (const page of ctx.pages()) if (!page.isClosed()) {
    report.pages.push({ url: page.url(), text: (await page.locator('body').innerText().catch(() => '')).slice(0,5000) })
    await page.screenshot({ path: fileURLToPath(new URL('failure.png', dir)), fullPage: true }).catch(() => {})
  }
  throw error
} finally {
  for (const name of Object.keys(fixture)) await control({ action: 'change', name, kind: 'restore' }).catch(() => {})
  for (const sid of sessions) await control({ action: 'expire', session_id: sid }).catch(() => {})
  for (const ctx of contexts) await ctx.close().catch(() => {})
  await browser.close()
  await writeFile(new URL('result.json', dir), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ source, status: report.status, cases: report.cases.length }))
}
