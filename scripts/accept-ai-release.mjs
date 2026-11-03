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
const dir = new URL('../output/ai-release/', import.meta.url)
await mkdir(dir, { recursive: true })
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const report = { source, origin, apiMocks: false, providerCalls: 0, cases: [] }
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
  await attestOfflineBackend(ctx, source, 'finite')
  contexts.push(ctx)
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
  assert.equal((await json(await ctx.request.get(origin + '/build-info.json'))).source, source)
  await json(await call(ctx, 'POST', 'ai-search/identity'))
  const state = await owned(ctx)
  const initial = body(state)
  const first = await json(await call(ctx, 'POST', 'ai-search/query', initial))
  assert.equal(first.operation.status, 'succeeded')
  assert.ok(first.cards.cards.total > 0)
  const repeated = await json(await call(ctx, 'POST', 'ai-search/query', initial))
  assert.deepEqual(repeated.operation.receipt, first.operation.receipt)
  assert.equal(repeated.operation.used, 1)
  assert.equal((await inspect(state)).calls, 1)
  pass('guest actual query + exact receipt replay: one parser call and debit')
  const page = await ctx.newPage()
  await page.addInitScript(() => { localStorage.setItem('112233:language:v1', 'es'); localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable') })
  await page.goto(origin, { waitUntil: 'networkidle' })
  await page.evaluate(value => sessionStorage.setItem('112233:ai-continuation:v1:guest', JSON.stringify(value)),
    { sessionId: state.session_id, resultRef: first.operation.receipt.result_ref })
  await page.reload({ waitUntil: 'networkidle' })
  await openAI(page)
  await page.waitForSelector('.ai-search-dialog__cards > div')
  assert.ok(await page.getByRole('dialog').evaluate(el => el.scrollWidth <= el.clientWidth + 1))
  await page.screenshot({ path: fileURLToPath(new URL('guest-mobile.png', dir)), fullPage: true })
  pass('actual mobile guest UI reload: owned continuation and cards, no horizontal overflow')
  for (const version of [1, 2]) {
    const result = await json(await call(ctx, 'POST', 'ai-search/query', body({ ...state, version })))
    assert.equal(result.operation.used, version + 1)
  }
  await json(await call(ctx, 'POST', 'ai-search/query', body({ ...state, version: 3 })), 429)
  assert.equal((await json(await call(ctx, 'GET', 'ai-search/quota'))).remaining, 0)
  pass('guest three successful operations; fourth rejected without debit')
  // Actual login UI. Token is kept only in memory for authenticated HTTP checks.
  await page.goto(origin + '/#/acceso')
  console.log('CHECK actual browser email login')
  await page.getByRole('button', { name: 'Iniciar sesión con email', exact: true }).click()
  await page.getByLabel('Email', { exact: true }).fill('acceptance-user@synthetic.example')
  await page.getByLabel('Contraseña', { exact: true }).fill('Synthetic-Lab-Only-2026!')
  const logged = page.waitForResponse(r => r.url().endsWith('/api/v1/auth/login'))
  await page.locator('form button[type=submit]').click()
  const auth = { Authorization: 'Bearer ' + (await json(await logged)).accessToken }
  await page.waitForURL(origin + '/#/')
  await openAI(page)
  assert.equal(await page.locator('.ai-search-dialog__cards > div').count(), 0)
  await json(await call(ctx, 'GET', 'ai-search/sessions/' + state.session_id, undefined, auth), 404)
  const before = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
  assert.equal(before.limit, 200)
  pass('actual browser login: auth quota 200, guest state not transferred')
  await labControl({ action: 'expire', session_id: state.session_id })
  const active = await owned(ctx, auth)
  for (const fault of ['failure', 'cancel', 'commit-ack', 'timeout']) {
    const version = active.version
    const request = body(active)
    const quota = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
    const callsBefore = (await inspect(active)).calls
    await arm(active, fault)
    const response = await call(ctx, 'POST', 'ai-search/query', request, auth)
    if (fault === 'commit-ack') {
      await json(response, 503)
      const replay = await json(await call(ctx, 'POST', 'ai-search/query', request, auth))
      assert.equal(replay.operation.status, 'succeeded'); assert.equal(replay.replay, true)
      active.version++
    } else if (fault === 'timeout') {
      await json(response, 504)
      // Maintenance, not the cancelled request, owns expired-lease recovery.
      let terminal
      for (let i = 0; i < 24; i++) {
        const observed = await inspect({ ...active, version })
        if (observed.requests.some(row => row.key === request.idempotency_key && row.status === 'failed')) { terminal = true; break }
        await sleep(5000)
      }
      assert.equal(terminal, true, 'maintenance must recover timed-out reservation')
      const replay = await json(await call(ctx, 'POST', 'ai-search/query', request, auth))
      assert.equal(replay.operation.status, 'failed')
    } else {
      if (fault === 'failure') assert.equal((await json(response)).operation.status, 'failed')
      else assert.ok([500, 503].includes(response.status()))
      assert.equal((await json(await call(ctx, 'POST', 'ai-search/query', request, auth))).operation.status, 'failed')
    }
    const after = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
    assert.equal(after.used, quota.used + (fault === 'commit-ack' ? 1 : 0))
    assert.equal(after.reserved, 0)
    // Each fault uses the same version until success; account for earlier calls.
    assert.equal((await inspect({ ...active, version })).calls, callsBefore + 1)
    pass('synthetic model ' + fault + ': actual HTTP lifecycle, durable retry and quota checked')
  }
  await page.locator('#ai-rental-mode').selectOption('none')
  let dropped = false, lostBody, committed
  await page.route('**/api/v1/ai-search/query', async route => {
    if (dropped) return route.continue()
    dropped = true
    lostBody = route.request().postDataJSON()
    const response = await route.fetch()
    assert.equal(response.status(), 200)
    committed = await response.json()
    await route.abort('failed')
  })
  await page.locator('#ai-search-text').fill('все варианты')
  const action = page.locator('.ai-search-dialog > .home-ai-search__action')
  await action.click()
  await page.getByRole('status').filter({ hasText: 'No se pudo' }).waitFor()
  const retried = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
  await action.click()
  const retry = await retried
  assert.deepEqual(retry.request().postDataJSON(), lostBody)
  const recovered = await json(retry)
  sessions.push(lostBody.session_id)
  assert.deepEqual(recovered.operation.receipt, committed.operation.receipt)
  assert.equal(recovered.operation.used, committed.operation.used)
  assert.equal((await inspect({ session_id: lostBody.session_id, version: 0 })).calls, 1)
  pass('real mobile browser disconnect after commit: exact retry restores receipt, no second inference or debit')
  const uiState = { session_id: lostBody.session_id, version: 1 }
  await arm(uiState, 'delay')
  await page.locator('#ai-search-text').fill('желательно с балконом')
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
  pass('real mobile browser cancel waiting: uncertain state, exact retry, one parser call')
  await page.screenshot({ path: fileURLToPath(new URL('auth-mobile.png', dir)), fullPage: true })
  const refresh = page.waitForResponse(r => r.url().endsWith('/auth/refresh'))
  await page.reload({ waitUntil: 'networkidle' })
  const refreshedIdentity = await json(await refresh)
  auth.Authorization = 'Bearer ' + refreshedIdentity.accessToken
  await openAI(page)
  await page.waitForSelector('.ai-search-dialog__cards > div')
  pass('authenticated browser refresh restores owned results')
  for (const service of ['redis', 'postgres']) {
    const quota = await json(await call(ctx, 'GET', 'ai-search/quota', undefined, auth))
    try {
      docker('stop', '--time', '5', 'ttest-ai-text-lab-' + service)
      const response = await call(ctx, 'GET', 'ai-search/quota', undefined, auth)
      assert.equal(response.status(), 503)
      assert.ok(response.headers()['cache-control'].includes('no-store'))
      if (service === 'postgres') await sleep(6000) // include a maintenance tick during the outage
      pass('real ' + service + ' outage: bounded 503, no-store and fail closed')
    } finally { docker('start', 'ttest-ai-text-lab-' + service) }
    let after
    for (let i = 0; i < 30; i++) {
      const response = await call(ctx, 'GET', 'ai-search/quota', undefined, auth)
      if (response.ok()) { after = await response.json(); break }
      await sleep(1000)
    }
    assert.equal(after.used, quota.used); assert.equal(after.reserved, quota.reserved)
    pass(service + ' restart: real quota restored unchanged')
  }
  report.snapshot = JSON.parse(docker('exec', 'ttest-ai-text-lab-backend', 'python', '-m', 'lab.release_status'))
  assert.equal(report.snapshot.recovery_overdue, 0)
  const metrics = docker('exec', 'ttest-ai-text-lab-backend', 'python', '-c',
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())")
  for (const privateValue of [...sessions, 'все варианты', 'acceptance-user@synthetic.example', auth.Authorization]) {
    assert.ok(!metrics.includes(privateValue))
  }
  assert.ok(metrics.includes('ttest_ai_execution_total'))
  assert.ok(metrics.includes('ttest_ai_parser_seconds_count'))
  assert.ok(metrics.includes('failure="timeout"'))
  await writeFile(new URL('metrics.prom', dir), metrics)
  pass('actual execution/parser metrics and aggregate queue/coverage/freshness snapshot; private canaries absent')
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'
  report.failure = { name: error.name, message: error.message.slice(0, 160) }
  for (const ctx of contexts) for (const page of ctx.pages()) {
    await page.screenshot({ path: fileURLToPath(new URL('failure.png', dir)), fullPage: true }).catch(() => {})
  }
  throw error
} finally {
  for (const sid of sessions) await labControl({ action: 'expire', session_id: sid }).catch(() => {})
  for (const ctx of contexts) await ctx.close()
  await browser.close()
  await writeFile(new URL('result.json', dir), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ source, status: report.status, cases: report.cases.length }))
}
