// Offline rehearsal of the exact proposed LIVE UI smoke. Provider bytes are
// synthetic fixtures; UI/HTTPS/backend/PostGIS/Redis/receipts are real.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'
import { labControl } from './ai-text-lab-control.mjs'
import { attestOfflineBackend } from './ai-lab-runtime.mjs'

assert.equal(process.argv.length, 2, 'This driver has no live/approval/key option. Offline rehearsal only.')
const origin = 'https://localhost:9443'
const corpus = JSON.parse(await readFile(new URL('../backend/lab/intent_cases.v1.json', import.meta.url), 'utf8'))
const cases = ['ru-balcony', 'es-monthly', 'en-negation'].map(id => corpus.find(c => c.id === id))
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const dir = new URL('../output/ai-closed-ui-rehearsal/' + crypto.randomUUID() + '/', import.meta.url)
await mkdir(dir, { recursive: true })
const report = { source, origin, mode: 'decision-transport-fixture', apiMocks: false,
  providerCalls: null, liveSmoke: 'NOT_RUN', status: 'RUNNING', runtimeAttestations: [],
  driverSha256: createHash('sha256').update(await readFile(fileURLToPath(import.meta.url))).digest('hex'), cases: [] }
const browser = await chromium.launch({ ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH
  ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}) })
const headers = { Origin: origin, 'X-AI-Request': '1' }
async function json(response) { assert.equal(response.status(), 200); return response.json() }
async function openAI(page) {
  for (let step = 0; step < 6; step++) {
    const entry = page.locator('.home-ai-search__action:visible, .m2-onboarding .m2-primary:visible, .m2-auth-skip:visible').first()
    await entry.waitFor()
    if (await page.locator('.home-ai-search__action:visible').count()) {
      await page.locator('.home-ai-search__action:visible').click(); return
    }
    await entry.click()
  }
  throw Error('onboarding incomplete')
}
try {
  for (const [index, testCase] of cases.entries()) {
    // Real guest issuance is 2/minute. Space fresh contexts; never reset buckets
    // or retry a model operation to work around admission limits.
    if (index > 0) await new Promise(resolve => setTimeout(resolve, 35000))
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 950 } })
    try {
      const attestation = await attestOfflineBackend(ctx, source)
      report.runtimeAttestations.push(attestation)
      report.providerCalls = attestation.verifiedProviderCalls
      const build = await json(await ctx.request.get(origin + '/build-info.json'))
      assert.equal(build.source, source); assert.equal(build.parser, 'decision-transport-fixture')
      const page = await ctx.newPage()
      await page.addInitScript(() => {
        localStorage.setItem('112233:language:v1', 'es')
        localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
      })
      await page.goto(origin, { waitUntil: 'networkidle' }); await openAI(page)
      await page.locator('#ai-rental-mode').selectOption('none')
      await page.locator('#ai-search-text').fill(testCase.text)
      const pending = page.waitForResponse(r => r.url().endsWith('/ai-search/query'))
      await page.locator('.ai-search-dialog > .home-ai-search__action').click()
      const response = await pending
      const answer = await json(response)
      assert.equal(answer.operation.status, 'succeeded')
      const payload = response.request().postDataJSON()
      const sid = payload.session_id
      const ref = answer.operation.receipt.result_ref
      const intent = (await json(await ctx.request.get(origin + '/api/v1/ai-search/sessions/' + sid))).intent
      assert.deepEqual(intent.criteria, testCase.expected)
      assert.equal(intent.version, 1)
      const before = await labControl({ action: 'inspect', session_id: sid, version: 0 })
      assert.equal(before.calls, 1)
      const replay = await json(await ctx.request.post(origin + '/api/v1/ai-search/query', { headers, data: payload }))
      assert.deepEqual(replay.operation.receipt, answer.operation.receipt)
      const map = await json(await ctx.request.post(origin + '/api/v1/ai-search/results/' + ref + '/map', {
        headers, data: { search: { west: -17, east: -16, south: 27, north: 29, zoom: 10 } } }))
      assert.equal(map.intent_hash, answer.cards.intent_hash)
      await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
      await page.reload({ waitUntil: 'networkidle' }); await openAI(page)
      await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
      const after = await labControl({ action: 'inspect', session_id: sid, version: 0 })
      assert.equal(after.calls, 1)
      const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))
      assert.ok(!stored.includes(testCase.text))
      await page.screenshot({ path: fileURLToPath(new URL(testCase.id + '.png', dir)), fullPage: true })
      report.cases.push({ id: testCase.id, passed: true, fixtureTransportAttempts: after.calls,
        exactRetryNoNewAttempt: true, reloadNoNewAttempt: true, cardsMapHashMatch: true,
        rawTextPersisted: false, total: answer.cards.cards.total })
      console.log('PASS ' + testCase.id)
    } finally { await ctx.close() }
  }
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'
  report.failure = { name: error.name, message: error.message.slice(0, 200) }
  throw error
} finally {
  await browser.close()
  await writeFile(new URL('result.json', dir), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' })
  console.log('Evidence: ' + fileURLToPath(dir))
}
