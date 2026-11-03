// Bounded release drill on the owned synthetic stack. Real HTTPS/UI/DB/Redis.
// Model faults are confined to lab.acceptance; no external providers or API mocks.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { labControl } from './ai-text-lab-control.mjs'
import { attestOfflineBackend } from './ai-lab-runtime.mjs'

const origin = 'https://localhost:9443'
const dir = new URL('../output/ai-review-fixes/', import.meta.url)
await mkdir(dir, { recursive: true })
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const report = { source, mode: 'decision-transport-fixture', origin, apiMocks: false, providerCalls: 0, cases: [] }
const pass = name => { report.cases.push({ name, passed: true }); console.log('PASS ' + name) }
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8', timeout: 30000 }).trim()
for (const name of ['backend', 'frontend', 'postgres', 'redis', 'maintenance']) {
  const labels = JSON.parse(docker('inspect', '--format', '{{json .Config.Labels}}', 'ttest-ai-text-lab-' + name))
  assert.equal(labels['es.ttest.purpose'], 'ai-text-synthetic-lab-v1')
}
const browser = await chromium.launch({ ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}) })
const contexts = []
const sessions = []
async function client() {
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 950 } })
  contexts.push(ctx)
  await attestOfflineBackend(ctx, source)
  ctx.setDefaultTimeout(20000)
  return ctx
}
async function call(ctx, method, path, data, auth = {}) {
  return ctx.request.fetch(origin + '/api/v1/' + path, { method, data,
    headers: { Origin: origin, 'X-AI-Request': '1', ...auth }, timeout: 25000 })
}
async function json(response, status = 200) {
  assert.equal(response.status(), status, 'unexpected HTTP status')
  return response.json()
}
async function owned(ctx, auth = {}) {
  const value = (await json(await call(ctx, 'POST', 'ai-search/sessions', { idempotency_key: crypto.randomUUID() }, auth))).intent
  sessions.push(value.session_id)
  return value
}
const body = state => ({ session_id: state.session_id, expected_version: state.version,
  idempotency_key: crypto.randomUUID(), text: 'все варианты', search: { limit: 6 } })
async function inspect(state) { return labControl({ action: 'inspect', session_id: state.session_id, version: state.version }) }
async function arm(state, fault) { return labControl({ action: 'arm', session_id: state.session_id, version: state.version, fault }) }
async function openAI(page) {
  // Login/reload can mount onboarding asynchronously after the hash changes.
  // Wait for one actual visible entry, rather than racing a count() snapshot.
  for (let i = 0; i < 6; i++) {
    const entry = page.locator('.home-ai-search__action:visible, .m2-onboarding .m2-primary:visible, .m2-auth-skip:visible').first()
    await entry.waitFor()
    if (await page.locator('.home-ai-search__action:visible').count()) {
      await page.locator('.home-ai-search__action:visible').click()
      return
    }
    await entry.click()
  }
  throw Error('mobile onboarding did not reach home')
}
try {
  const ctx = await client()
  const build = await json(await ctx.request.get(origin + '/build-info.json'))
  assert.equal(build.source, source)
  assert.equal(build.parser, 'decision-transport-fixture')
  const page = await ctx.newPage()
  await page.addInitScript(() => { localStorage.setItem('112233:language:v1', 'es'); localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable') })
  await page.goto(origin, { waitUntil: 'networkidle' })
  await openAI(page)
  await page.locator('[data-ai-lab-mode="decision-transport-fixture"]').waitFor()
  await page.locator('#ai-rental-mode').selectOption('holiday')
  const action = page.locator('.ai-search-dialog > .home-ai-search__action')
  let current, receipt, sid, cardsHash
  for (const text of ['с маленькой собакой', 'до 60 евро за ночь', 'желательно с балконом']) {
    await page.locator('#ai-search-text').fill(text)
    const response = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
    await action.click()
    const result = await json(await response)
    assert.equal(result.operation.status, 'succeeded')
    cardsHash = result.cards.intent_hash
    receipt = result.operation.receipt
    sid = (await (await response).request().postDataJSON()).session_id
    if (!sessions.includes(sid)) sessions.push(sid)
    const exact = await json(await call(ctx, 'POST', 'ai-search/query', (await response).request().postDataJSON()))
    assert.deepEqual(exact.operation.receipt, receipt)
    await json(await call(ctx, 'POST', 'ai-search/query', { ...(await response).request().postDataJSON(), text: 'ничего не менять' }), 409)
    current = (await json(await call(ctx, 'GET', 'ai-search/sessions/' + sid))).intent
    assert.equal(current.criteria.pets.strength, 'hard')
    if (current.version >= 2) assert.equal(current.criteria.budget.strength, 'hard')
    await page.waitForSelector('.ai-search-dialog__cards > div')
  }
  assert.equal(current.version, 3)
  assert.equal(current.criteria.balcony.strength, 'soft')
  const map = await json(await call(ctx, 'POST', 'ai-search/results/' + receipt.result_ref + '/map', {
    search: { west: -17, east: -16, south: 27, north: 29, zoom: 10 } }))
  assert.equal(map.intent_hash, cardsHash)
  assert.ok(map.map.items.length > 0)
  assert.equal((await json(await call(ctx, 'GET', 'ai-search/quota'))).used, 3)
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  assert.ok(await page.locator('.ai-search-dialog__cards').isHidden())
  await page.getByRole('region', { name: 'Локальная координатная карта' }).waitFor()
  await page.getByRole('button', { name: 'Ver lista', exact: true }).click()
  pass('actual mobile exclusive map/list toggle')
  await page.locator('.ai-search-dialog__cards').scrollIntoViewIfNeeded()
  await page.screenshot({ path: fileURLToPath(new URL('guest-cards.png', dir)), fullPage: true })
  pass('real mobile UI -> decision adapter -> typed intent -> owned PG cards/map: hard criteria and guest quota3')
  const refreshGuest = page.waitForResponse(r => r.url().endsWith('/ai-search/sessions/' + sid))
  await page.reload({ waitUntil: 'networkidle' }); await openAI(page); await json(await refreshGuest)
  await page.waitForSelector('.ai-search-dialog__cards > div')
  const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))
  for (const text of ['с маленькой собакой', 'до 60 евро за ночь', 'желательно с балконом']) assert.ok(!stored.includes(text))
  pass('guest reload recovery and raw text absent from browser durable storage')
  await page.goto(origin + '/#/acceso')
  await page.getByRole('button', { name: 'Iniciar sesión con email', exact: true }).click()
  await page.getByLabel('Email', { exact: true }).fill('acceptance-user@synthetic.example')
  await page.getByLabel('Contraseña', { exact: true }).fill('Synthetic-Lab-Only-2026!')
  const logged = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'))
  await page.locator('form button[type=submit]').click()
  const auth = { Authorization: 'Bearer ' + (await json(await logged)).accessToken }
  await page.waitForURL(origin + '/#/'); await openAI(page)
  await json(await call(ctx, 'GET', 'ai-search/sessions/' + sid, undefined, auth), 404)
  await labControl({ action: 'expire', session_id: sid })
  let state
  await page.locator('#ai-rental-mode').selectOption('none')
  let lastAttempt = 0
  async function send(text, fault) {
    await sleep(Math.max(0, 11000 - (Date.now() - lastAttempt))); lastAttempt = Date.now()
    if (fault) await arm(state, fault)
    const before = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
    const count = state ? (await inspect(state)).calls : 0
    if (!fault) {
      await page.locator('#ai-search-text').fill(text)
      const waiting = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
      await action.click()
      const response = await waiting
      const request = response.request().postDataJSON()
      if (!state) { state = { session_id: request.session_id, version: request.expected_version }; sessions.push(state.session_id) }
      await page.getByRole('status').waitFor()
      return { request, before, count, response }
    }
    const request = { ...body(state), text }
    const response = await call(ctx, 'POST', 'ai-search/query', request, auth)
    return { request, before, count, response }
  }
  for (const [text, code] of [['уточнить бюджет', 'INTENT_CLARIFICATION_REQUIRED'], ['ничего не менять', 'INTENT_NO_CHANGE'], ['рядом с хорошими людьми', 'INTENT_UNSUPPORTED']]) {
    const { request, before, count, response } = await send(text)
    const result = await json(response)
    assert.equal(result.operation.failure_code, code)
    await page.getByRole('status').filter({ hasText: { INTENT_CLARIFICATION_REQUIRED: 'Aclara', INTENT_NO_CHANGE: 'no cambia', INTENT_UNSUPPORTED: 'Reformula' }[code] }).waitFor()
    const replay = await json(await call(ctx, 'POST', 'ai-search/query', request, auth))
    assert.equal(replay.operation.failure_code, code)
    assert.equal(replay.operation.used, before.used)
    assert.equal((await inspect(state)).calls, count + 1)
    assert.equal((await json(await call(ctx, 'GET', 'ai-search/sessions/' + state.session_id, undefined, auth))).intent.version, 0)
    pass(code + ': actual UI fixed message, unchanged version, free terminal receipt, retry without model IO')
  }
  for (const fault of ['failure', 'cancel', 'timeout', 'commit-ack']) {
    const { request, before, count, response } = await send('обязательно с балконом', fault)
    if (fault === 'commit-ack') {
      await json(response, 503)
      const replay = await json(await call(ctx, 'POST', 'ai-search/query', request, auth))
      assert.equal(replay.operation.status, 'succeeded')
      assert.equal(replay.operation.used, before.used + 1)
      state.version++
    } else {
      if (fault === 'cancel') await json(response, 503)
      else assert.equal((await json(response)).operation.failure_code, 'LLM_FAILURE')
      const replay = await json(await call(ctx, 'POST', 'ai-search/query', request, auth))
      assert.equal(replay.operation.status, 'failed')
      assert.equal(replay.operation.used, before.used)
    }
    assert.equal((await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))).reserved, 0)
    assert.equal((await inspect({ ...state, version: fault === 'commit-ack' ? state.version - 1 : state.version })).calls, count + 1)
    pass('model transport ' + fault + ': bounded HTTP lifecycle, exact retry, one model attempt and expected debit')
  }
  // Stale version is rejected before the model transport.
  const stale = { ...body({ ...state, version: 0 }), text: 'с маленькой собакой' }
  await json(await call(ctx, 'POST', 'ai-search/query', stale, auth), 409)
  pass('ownership and stale version rejected before inference')
  const refreshed = page.waitForResponse(r => r.url().endsWith('/auth/refresh'))
  await page.reload({ waitUntil: 'networkidle' })
  auth.Authorization = 'Bearer ' + (await json(await refreshed)).accessToken
  await openAI(page)
  await page.locator('#ai-rental-mode').selectOption('none')
  let lost, committed, dropped = false
  await page.route('**/api/v1/ai-search/query', async route => {
    if (dropped) return route.continue()
    dropped = true; lost = route.request().postDataJSON()
    const response = await route.fetch(); committed = await response.json(); await route.abort('failed')
  })
  await sleep(11000)
  await page.locator('#ai-search-text').fill('обязательно с балконом')
  await action.click()
  await page.getByRole('status').filter({ hasText: 'No se pudo' }).waitFor()
  const pendingStored = await page.evaluate(() => JSON.stringify({ ...sessionStorage }))
  assert.ok(pendingStored.includes(lost.idempotency_key))
  assert.ok(!pendingStored.includes(lost.text) && !pendingStored.includes('criteria'))
  const operationRead = page.waitForResponse(r => r.url().endsWith('/ai-search/operations/' + lost.idempotency_key))
  const refreshedAfterLoss = page.waitForResponse(r => r.url().endsWith('/auth/refresh'))
  await page.reload({ waitUntil: 'networkidle' })
  auth.Authorization = 'Bearer ' + (await json(await refreshedAfterLoss)).accessToken
  await openAI(page)
  const recovered = await json(await operationRead)
  assert.deepEqual(recovered.receipt, committed.operation.receipt)
  await page.waitForSelector('.ai-search-dialog__cards > div')
  sessions.push(lost.session_id)
  assert.equal((await inspect({ session_id: lost.session_id, version: 0 })).calls, 1)
  pass('real commit -> lost ACK -> hard reload -> owned operation receipt/cards: one inference and debit, no stored raw text')
  await page.unroute('**/api/v1/ai-search/query')
  await sleep(11000)
  const uiState = { session_id: lost.session_id, version: 1 }
  await arm(uiState, 'delay')
  await page.locator('#ai-search-text').fill('с маленькой собакой')
  const sent = page.waitForRequest(r => r.url().endsWith('/ai-search/query'))
  await action.click()
  const cancelBody = (await sent).postDataJSON()
  for (let i = 0; i < 20 && !(await inspect(uiState)).calls; i++) await sleep(100)
  await page.getByRole('button', { name: 'Dejar de esperar', exact: true }).click()
  await sleep(3300)
  const checked = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
  await action.click()
  const checkedResponse = await checked
  assert.deepEqual(checkedResponse.request().postDataJSON(), cancelBody)
  assert.equal((await json(checkedResponse)).operation.status, 'succeeded')
  assert.equal((await inspect(uiState)).calls, 1)
  pass('browser cancel waiting during model transport: uncertain state and exact one-inference recovery')
  await sleep(11000)
  const beforeMetadata = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
  let metadataDropped = false
  await page.route('**/api/v1/ai-search/results/*', async route => {
    if (metadataDropped) return route.continue()
    metadataDropped = true
    const real = await route.fetch(); assert.equal(real.status(), 200)
    await route.abort('failed')
  })
  await page.locator('#ai-search-text').fill('до 60 евро за ночь')
  await action.click()
  await page.getByRole('button', { name: 'Reintentar sincronización', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Reintentar sincronización', exact: true }).click()
  await page.waitForSelector('.ai-search-dialog__cards > div')
  assert.equal((await inspect({ session_id: lost.session_id, version: 2 })).calls, 1)
  assert.equal((await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))).used, beforeMetadata.used + 1)
  pass('real committed receipt survives lost metadata response: read-only retry, one inference/debit')
  await page.screenshot({ path: fileURLToPath(new URL('auth-recovery.png', dir)), fullPage: true })
  const metrics = docker('exec', 'ttest-ai-text-lab-backend', 'python', '-c', "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())")
  for (const secret of [...sessions, auth.Authorization, 'с маленькой собакой', 'уточнить бюджет']) assert.ok(!metrics.includes(secret))
  pass('actual metrics exclude raw text, session IDs and tokens')
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'; report.failure = { name: error.name, message: error.message.slice(0, 200) }
  for (const ctx of contexts) for (const page of ctx.pages()) await page.screenshot({ path: fileURLToPath(new URL('failure.png', dir)), fullPage: true }).catch(() => {})
  throw error
} finally {
  for (const sid of sessions) await labControl({ action: 'expire', session_id: sid }).catch(() => {})
  for (const ctx of contexts) await ctx.close()
  await browser.close()
  await writeFile(new URL('result.json', dir), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ source, status: report.status, cases: report.cases.length }))
}
