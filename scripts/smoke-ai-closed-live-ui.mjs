// Explicitly authorized three-case LIVE synthetic smoke. No provider API mocks.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

assert.equal(process.argv.length, 3, 'Explicit reviewed run manifest required')
const manifestPath = path.resolve(process.argv[2])
const run = JSON.parse(await readFile(manifestPath, 'utf8'))
assert.equal(run.approval, 'deepseek-synthetic-ui-smoke-v1')
assert.equal(run.authorizedDateMoscow, '2026-11-03')
const origin = 'https://localhost:9443'
const corpusBytes = await readFile(new URL('../backend/lab/intent_cases.v1.json', import.meta.url))
assert.equal(createHash('sha256').update(corpusBytes).digest('hex'),
  '7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288')
const corpus = JSON.parse(corpusBytes)
const cases = ['ru-balcony', 'es-monthly', 'en-negation'].map(id => corpus.find(c => c.id === id))
const dir = path.dirname(manifestPath)
function budget() {
  const code = `import sqlite3,json,sys,pathlib
p=pathlib.Path(sys.argv[1]).resolve(strict=True)
with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as db:
 row=db.execute('SELECT count(*),coalesce(sum(reserved),0),count(prompt_tokens),coalesce(sum(prompt_tokens),0),coalesce(sum(completion_tokens),0) FROM attempts').fetchone()
 binding=db.execute('SELECT corpus FROM binding WHERE id=1').fetchone()[0]
 print(json.dumps(dict(zip(['attempts','reserved_micro_usd','observed_usage_attempts','prompt_tokens','completion_tokens'],row))|{'corpus_sha256':binding}))`
  return JSON.parse(execFileSync(run.python, ['-c', code, run.journal], { encoding: 'utf8', timeout: 10000 }))
}
const before = budget()
assert.equal(before.attempts, 51)
assert.equal(before.reserved_micro_usd, 564060)
assert.equal(before.corpus_sha256, createHash('sha256').update(corpusBytes).digest('hex'))
await writeFile(path.join(dir, 'smoke-started.json'), JSON.stringify({ source: run.source, before }) + '\n', { flag: 'wx' })
const report = { source: run.source, origin, mode: 'LIVE_SYNTHETIC', apiMocks: false,
  status: 'RUNNING', before, cases: [], driverSha256: createHash('sha256')
    .update(await readFile(fileURLToPath(import.meta.url))).digest('hex') }
const browser = await chromium.launch({ executablePath: run.chrome })
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
    if (index > 0) await new Promise(resolve => setTimeout(resolve, 35000))
    assert.equal(budget().attempts, 51 + index, 'Unexpected attempts: STOP, never compensate with new calls')
    const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 950 } })
    let operationKey
    try {
      const build = await json(await ctx.request.get(origin + '/build-info.json'))
      assert.equal(build.source, run.source); assert.equal(build.parser, 'closed-live-synthetic')
      const page = await ctx.newPage()
      await page.addInitScript(() => {
        localStorage.setItem('112233:language:v1', 'es')
        localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
      })
      page.on('request', request => {
        if (request.url().endsWith('/ai-search/query')) operationKey = request.postDataJSON().idempotency_key
      })
      await page.goto(origin, { waitUntil: 'networkidle' }); await openAI(page)
      await expect(page.locator('[data-ai-lab-mode="closed-live-synthetic"]')).toBeVisible()
      await page.locator('#ai-rental-mode').selectOption('none')
      await page.locator('#ai-search-text').fill(testCase.text)
      const pending = page.waitForResponse(r => r.url().endsWith('/ai-search/query'), { timeout: 25000 })
      await page.locator('.ai-search-dialog > .home-ai-search__action').click()
      const response = await pending
      const answer = await json(response)
      assert.equal(answer.operation.status, 'succeeded', 'STOP on failed/uncertain outcome; no new model call')
      assert.equal(budget().attempts, 52 + index)
      const payload = response.request().postDataJSON()
      const intent = (await json(await ctx.request.get(origin + '/api/v1/ai-search/sessions/' + payload.session_id))).intent
      assert.deepEqual(intent.criteria, testCase.expected); assert.equal(intent.version, 1)
      const status = await json(await ctx.request.get(origin + '/api/v1/ai-search/operations/' + operationKey))
      assert.equal(status.status, 'succeeded')
      const replay = await json(await ctx.request.post(origin + '/api/v1/ai-search/query', { headers, data: payload }))
      assert.deepEqual(replay.operation.receipt, answer.operation.receipt)
      assert.equal(budget().attempts, 52 + index)
      const map = await json(await ctx.request.post(origin + '/api/v1/ai-search/results/' + status.receipt.result_ref + '/map', {
        headers, data: { search: { west: -17, east: -16, south: 27, north: 29, zoom: 10 } } }))
      assert.equal(map.intent_hash, answer.cards.intent_hash)
      await page.reload({ waitUntil: 'networkidle' }); await openAI(page)
      await expect(page.getByRole('region', { name: 'Resultados confirmados' })).toBeVisible()
      assert.equal(budget().attempts, 52 + index)
      const quota = await json(await ctx.request.get(origin + '/api/v1/ai-search/quota'))
      assert.equal(quota.used, 1)
      const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }))
      assert.ok(!stored.includes(testCase.text))
      await page.screenshot({ path: path.join(dir, testCase.id + '.png'), fullPage: true })
      report.cases.push({ id: testCase.id, passed: true, cumulativeAttempts: budget().attempts,
        statusReadBeforeReplay: true, exactRetryNoNewAttempt: true, reloadNoNewAttempt: true,
        cardsMapHashMatch: true, rawTextPersisted: false, debit: quota.used, total: answer.cards.cards.total })
      console.log('PASS ' + testCase.id)
    } catch (error) {
      if (operationKey) {
        // Read-only reconciliation only. Never repeat an uncertain provider operation.
        const result = await ctx.request.get(origin + '/api/v1/ai-search/operations/' + operationKey).catch(() => null)
        report.lastOperation = result?.ok() ? { status: (await result.json()).status } : { status: 'unavailable' }
      }
      throw error
    } finally { await ctx.close() }
  }
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'
  report.failure = { name: error.name, message: error.message.slice(0, 200) }
  throw error
} finally {
  await browser.close()
  report.after = budget()
  report.newAttempts = report.after.attempts - before.attempts
  assert.ok(report.newAttempts <= 3 && report.after.reserved_micro_usd <= 597240)
  await writeFile(path.join(dir, 'result.json'), JSON.stringify(report, null, 2) + '\n', { flag: 'wx' })
  console.log(JSON.stringify({ status: report.status, cases: report.cases.length, newAttempts: report.newAttempts }))
}
