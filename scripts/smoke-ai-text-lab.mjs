// Real Chromium + UI + HTTPS + backend + PostGIS + Redis. No route/API mocks.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { chromium, request, expect } from '@playwright/test'

const origin = 'https://localhost:9443'
const out = new URL('../output/ai-text-lab-smoke/', import.meta.url)
await mkdir(out, { recursive: true })
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const expected = {
  all: ['0f721c39-b8cf-5879-bea1-522514de63d1', 'a242160c-aa54-5e29-bde3-9a53ac8b5674',
    'a9fa78c3-7515-5a80-bb79-4bc5770c0e03', '36c2741e-0d7c-5610-bbbe-19f32de52155'],
  dog: ['0f721c39-b8cf-5879-bea1-522514de63d1', 'a242160c-aa54-5e29-bde3-9a53ac8b5674'],
  dog600: ['0f721c39-b8cf-5879-bea1-522514de63d1'],
}
const headers = { Origin: origin, 'X-AI-Request': '1' }
const evidence = { source, url: origin, parser: 'synthetic-exact-phrases-v1 (not LLM)',
  apiMocks: false, checks: [], externalRequests: [], browserErrors: [] }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 1100 } })
const api = context.request
const page = await context.newPage()
page.on('request', req => { if (new URL(req.url()).origin !== origin) evidence.externalRequests.push(req.url()) })
page.on('pageerror', error => evidence.browserErrors.push(error.message))
await page.addInitScript(() => {
  localStorage.setItem('112233:language:v1', 'es')
  localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
})
async function json(response, status = 200) {
  assert.equal(response.status(), status, await response.text())
  return response.json()
}
async function post(path, data, client = api, extra = {}) {
  return client.post(origin + '/api/v1' + path, { headers: { ...headers, ...extra }, data })
}
function ids(items) { return items.map(item => item.id).sort() }
const record = (check, details = {}) => evidence.checks.push({ check, ...details, passed: true })
try {
  assert.equal((await json(await api.get(origin + '/build-info.json'))).source, source)
  await page.goto(origin, { waitUntil: 'networkidle' })
  await expect(page.getByText(/Закрытый synthetic стенд/)).toBeVisible()
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-rental-mode').selectOption('long')
  let initialBody, initialAnswer, finalAnswer
  async function submit(phrase, first, expectedIds) {
    await page.locator('#ai-search-text').fill(phrase)
    const pending = page.waitForResponse(r => r.url() === origin + '/api/v1/ai-search/query')
    await page.getByRole('button', { name: first ? 'Buscar habitaciones' : 'Actualizar búsqueda', exact: true }).click()
    const response = await pending
    const answer = await json(response)
    assert.equal(answer.operation.status, 'succeeded', JSON.stringify(answer))
    assert.deepEqual(ids(answer.cards.cards.items), [...expectedIds].sort())
    assert.equal(answer.cards.cards.total, expectedIds.length)
    await expect(page.locator('.ai-search-dialog__cards > div')).toHaveCount(expectedIds.length)
    if (first) { initialBody = response.request().postDataJSON(); initialAnswer = answer }
    finalAnswer = answer
    record('browser query + real SQL cards', { phrase, ids: ids(answer.cards.cards.items), count: expectedIds.length })
    return answer
  }
  await submit('все варианты', true, expected.all)
  const cookie = (await context.cookies()).find(c => c.name === 'ai_search_guest')
  assert.ok(cookie?.secure && cookie.httpOnly && cookie.sameSite === 'Strict')
  record('Secure HttpOnly Strict guest cookie over HTTPS')
  await submit('с маленькой собакой', false, expected.dog)
  await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toContainText('Perro')
  await page.getByRole('button', { name: 'Ver mapa', exact: true }).click()
  await expect(page.getByText('Маркеров: 2', { exact: true })).toBeVisible()
  assert.deepEqual(await page.getByRole('region', { name: 'Локальная координатная карта' }).locator('[data-listing-id]')
    .evaluateAll(nodes => nodes.map(n => n.dataset.listingId).sort()), expected.dog.sort())
  const localMap = page.getByRole('region', { name: 'Локальная координатная карта' })
  await localMap.locator('[role="button"]').first().click()
  await expect(localMap).toContainText('Выбран ID:')
  await localMap.screenshot({ path: new URL('dog-map.png', out).pathname.replace(/^\/([A-Za-z]:)/, '$1') })
  await localMap.getByRole('button', { name: 'Масштаб 14' }).click()
  await expect(page.getByText('Маркеров: 2', { exact: true })).toBeVisible()
  await localMap.getByRole('button', { name: 'Сдвинуть область' }).click()
  await expect(page.getByText('Маркеров: 0', { exact: true })).toBeVisible()
  await localMap.getByRole('button', { name: 'Сдвинуть область' }).click()
  await expect(page.getByText('Маркеров: 2', { exact: true })).toBeVisible()
  record('real map viewport query + local zoom/pan + marker selection')
  const final = await submit('до 600 евро в месяц', false, expected.dog600)
  await expect(page.getByText('Маркеров: 1', { exact: true })).toBeVisible()
  const ref = final.operation.receipt.result_ref
  const meta = await json(await api.get(origin + '/api/v1/ai-search/results/' + ref))
  assert.equal(meta.intent.version, 3)
  assert.equal(meta.intent.criteria.budget.value.amount, '600')
  assert.equal(meta.intent.criteria.pets.strength, 'hard')
  record('follow-up preserves typed hard criteria + map', { criteria: meta.intent.criteria })
  await localMap.screenshot({ path: new URL('budget-map.png', out).pathname.replace(/^\/([A-Za-z]:)/, '$1') })
  await page.locator('.ai-search-dialog__cards').screenshot({ path: new URL('budget-card.png', out).pathname.replace(/^\/([A-Za-z]:)/, '$1') })
  const sid = initialBody.session_id
  const replay = await json(await post('/ai-search/query', initialBody))
  assert.equal(replay.replay, true); assert.equal(replay.operation.used, 3)
  assert.deepEqual(replay.operation.receipt, initialAnswer.operation.receipt)
  const quota = await json(await api.get(origin + '/api/v1/ai-search/quota'))
  assert.equal(quota.used, 3); assert.equal(quota.reserved, 0); assert.equal(quota.remaining, 0)
  await json(await post('/ai-search/query', { ...initialBody, expected_version: 3, idempotency_key: crypto.randomUUID() }), 429)
  record('quota 3/day + zero debit reads + idempotent replay', { quota })
  const page1 = await json(await post(`/ai-search/results/${initialAnswer.operation.receipt.result_ref}/cards`, { search: { limit: 1 } }))
  assert.equal(page1.cards.total, 4); assert.ok(page1.cards.nextCursor)
  const page2 = await json(await post(`/ai-search/results/${initialAnswer.operation.receipt.result_ref}/cards`, { search: { limit: 1, cursor: page1.cards.nextCursor } }))
  assert.notEqual(page1.cards.items[0].id, page2.cards.items[0].id)
  await json(await post(`/ai-search/results/${initialAnswer.operation.receipt.result_ref}/cards`, { search: { limit: 1, cursor: page1.cards.nextCursor + 'x' } }), 409)
  const ownedMap = await json(await post(`/ai-search/sessions/${sid}/map`, { expected_version: 3,
    search: { north: 28.2, south: 28.05, west: -16.8, east: -16.65, zoom: 14 } }))
  assert.deepEqual(ids(ownedMap.map.items), expected.dog600)
  await json(await post(`/ai-search/sessions/${sid}/cards`, { expected_version: 3, search: { limit: 1 } }))
  record('owned session/result/card/map reads + signed pagination')
  await json(await api.post(origin + '/api/v1/ai-search/identity', { headers: { ...headers, Origin: 'https://attacker.invalid' } }), 403)
  await json(await api.post(origin + '/api/v1/ai-search/identity', { headers: { Origin: origin } }), 403)
  const other = await request.newContext({ ignoreHTTPSErrors: true })
  try {
    await json(await post('/ai-search/identity', undefined, other))
    await json(await other.get(origin + '/api/v1/ai-search/sessions/' + sid), 404)
    await json(await post(`/ai-search/results/${ref}/cards`, {}, other), 404)
    const login = await json(await post('/auth/login', { email: 'user@synthetic.example', password: 'Synthetic-Lab-Only-2026!' }, other))
    const auth = { Authorization: 'Bearer ' + login.accessToken }
    await json(await other.get(origin + '/api/v1/ai-search/sessions/' + sid, { headers: auth }), 404)
    const before = await json(await other.get(origin + '/api/v1/ai-search/quota', { headers: auth }))
    assert.ok(before.remaining >= 5, 'synthetic auth quota has fewer than five operations remaining')
    // Reuse the same owned test session across smoke reruns; never reset quota.
    const session = await json(await post('/ai-search/sessions', { idempotency_key: 'c3ddbe7a-53d3-480d-afba-51ac1cb17f39', rental_mode: 'long' }, other, auth))
    let version = session.intent.version
    for (const [phrase, count] of [['все варианты', 4], ['с маленькой собакой', 2], ['до 400 евро в месяц', 0], ['все варианты', 4], ['обязательно с балконом', 0]]) {
      const result = await json(await post('/ai-search/query', { session_id: session.intent.session_id, expected_version: version++,
        idempotency_key: crypto.randomUUID(), text: phrase, search: { limit: 6 } }, other, auth))
      assert.equal(result.operation.status, 'succeeded', JSON.stringify(result))
      assert.equal(result.operation.limit, 200); assert.equal(result.cards.cards.total, count)
    }
    record('auth login + own session + 200/day + incompatible hard criteria + missing facts')
    const unsupported = await json(await post('/ai-search/query', { session_id: session.intent.session_id, expected_version: version,
      idempotency_key: crypto.randomUUID(), text: 'unsupported model instruction', search: { limit: 6 } }, other, auth))
    assert.equal(unsupported.operation.status, 'failed'); assert.equal(unsupported.operation.used, before.used + 5)
    record('unsupported deterministic phrase fails without debit')
  } finally { await other.dispose() }
  record('foreign guest/auth ownership + origin + CSRF rejection')
  const manual = await json(await post('/listings/search/cards', { rentalMode: 'long', limit: 20 }))
  assert.ok(manual.total >= 4)
  record('ordinary public search uses existing API path', { total: manual.total })
  assert.deepEqual(evidence.externalRequests, [])
  assert.deepEqual(evidence.browserErrors, [])
  record('no external browser requests or page errors')
  evidence.status = 'PASS'
} catch (error) {
  evidence.status = 'FAIL'; evidence.failure = String(error.stack || error)
  await page.screenshot({ path: new URL('failure.png', out).pathname.replace(/^\/([A-Za-z]:)/, '$1'), fullPage: true }).catch(() => {})
  throw error
} finally {
  await writeFile(new URL('result.json', out), JSON.stringify(evidence, null, 2) + '\n')
  await browser.close()
  console.log(JSON.stringify({ status: evidence.status, source, checks: evidence.checks.length, output: out.href }))
}
