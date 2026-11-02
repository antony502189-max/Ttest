// Reversible binary rollback and kill switch on the labelled local lab only.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { request } from '@playwright/test'
import { labControl } from './ai-text-lab-control.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const dir = new URL('../output/ai-release/', import.meta.url)
await mkdir(dir, { recursive: true })
const state = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8'))
const previous = 'f92829570a95d7c0b693caae39686e4828e95355'
const report = { source: state.source, rollbackSource: previous, cases: [], providerCalls: 0 }
const pass = (name, details = {}) => { report.cases.push({ name, ...details, passed: true }); console.log('PASS ' + name) }
const exec = (program, args) => execFileSync(program, args, { cwd: root, encoding: 'utf8', timeout: 90000, stdio: ['ignore', 'pipe', 'pipe'] }).trim()
const docker = (...args) => exec('docker', args)
for (const name of ['backend', 'frontend', 'postgres', 'redis', 'maintenance']) {
  assert.equal(JSON.parse(docker('inspect', '--format', '{{json .Config.Labels}}', 'ttest-ai-text-lab-' + name))['es.ttest.purpose'], 'ai-text-synthetic-lab-v1')
}
const volumes = JSON.parse(docker('inspect', 'ttest-ai-text-lab-postgres', 'ttest-ai-text-lab-backend'))
  .flatMap(c => c.Mounts.filter(m => m.Type === 'volume').map(m => m.Name)).sort()
const compose = ['compose', '--project-name', 'ttest-ai-text-lab', '-f', state.snapshot + '/deploy/ai-text-lab/compose.yml']
process.env.LAB_SOURCE_SHA = state.source
process.env.LAB_BACKEND_BASE = state.backendBase
process.env.LAB_FRONTEND_BASE = state.frontendBase
process.env.LAB_AI_DISABLED = 'false'
const override = fileURLToPath(new URL('rollback.json', dir))
await writeFile(override, JSON.stringify({ services: { backend: { image: 'ttest-ai-text-lab-backend:' + previous,
  labels: { 'org.opencontainers.image.revision': previous } } } }))
const api = await request.newContext({ baseURL: 'https://localhost:9443', ignoreHTTPSErrors: true, timeout: 25000,
  extraHTTPHeaders: { Origin: 'https://localhost:9443', 'X-AI-Request': '1' } })
async function json(response, status = 200) { assert.equal(response.status(), status); return response.json() }
async function ordinary() {
  const response = await api.post('/api/v1/listings/search/cards', { data: { limit: 6 } })
  const value = await json(response)
  assert.ok(value.total > 0)
  return value.total
}
let sid
try {
  assert.equal((await json(await api.get('/api/v1/ai-search/capabilities'))).text, true)
  const logged = await json(await api.post('/api/v1/auth/login', { data: {
    email: 'acceptance-user@synthetic.example', password: 'Synthetic-Lab-Only-2026!' } }))
  const headers = { Authorization: 'Bearer ' + logged.accessToken }
  const intent = (await json(await api.post('/api/v1/ai-search/sessions', { headers,
    data: { idempotency_key: crypto.randomUUID() } }))).intent
  sid = intent.session_id
  const data = { idempotency_key: crypto.randomUUID(), session_id: sid, expected_version: 0,
    text: 'все варианты', search: { limit: 6 } }
  const original = await json(await api.post('/api/v1/ai-search/query', { headers, data }))
  assert.equal(original.operation.status, 'succeeded', original.operation.failure_code)
  const total = await ordinary()
  try {
    const start = performance.now()
    docker(...compose, '-f', override, 'up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', 'backend')
    docker(...compose, 'restart', 'frontend')
    assert.equal(docker('inspect', '--format', '{{index .Config.Labels "org.opencontainers.image.revision"}}', 'ttest-ai-text-lab-backend'), previous)
    assert.equal(await ordinary(), total)
    const replay = await json(await api.post('/api/v1/ai-search/query', { headers, data }))
    assert.deepEqual(replay.operation.receipt, original.operation.receipt)
    assert.equal(replay.operation.used, original.operation.used)
    assert.equal(docker('exec', 'ttest-ai-text-lab-postgres', 'psql', '-U', 'ai_lab', '-d', 'ai_text_lab', '-Atc', 'SELECT version_num FROM alembic_version'), '0079_ai_operating_policy')
    pass('previous binary against current 0079: ordinary search and exact AI receipt replay', { switchSeconds: Math.round((performance.now() - start) / 1000) })
  } finally {
    docker(...compose, 'up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', 'backend')
    docker(...compose, 'restart', 'frontend')
  }
  const replay = await json(await api.post('/api/v1/ai-search/query', { headers, data }))
  assert.deepEqual(replay.operation.receipt, original.operation.receipt)
  assert.equal(replay.operation.used, original.operation.used)
  pass('forward binary restored: receipt and quota preserved')
  try {
    const start = performance.now()
    exec('pwsh.exe', ['-NoProfile', '-File', 'scripts/ai-text-lab.ps1', 'disable-ai'])
    assert.equal((await json(await api.get('/api/v1/ai-search/capabilities'))).text, false)
    assert.equal((await json(await api.post('/api/v1/ai-search/query', { headers, data }), 503)).detail, 'AI_SEARCH_DISABLED')
    assert.equal(await ordinary(), total)
    pass('AI kill switch: disabled capability + 503 while ordinary SQL search stays available', { switchSeconds: Math.round((performance.now() - start) / 1000) })
  } finally { exec('pwsh.exe', ['-NoProfile', '-File', 'scripts/ai-text-lab.ps1', 'enable-ai']) }
  assert.equal((await json(await api.get('/api/v1/ai-search/capabilities'))).text, true)
  const after = await json(await api.post('/api/v1/ai-search/query', { headers, data }))
  assert.deepEqual(after.operation.receipt, original.operation.receipt)
  assert.equal(after.operation.used, original.operation.used)
  const afterVolumes = JSON.parse(docker('inspect', 'ttest-ai-text-lab-postgres', 'ttest-ai-text-lab-backend'))
    .flatMap(c => c.Mounts.filter(m => m.Type === 'volume').map(m => m.Name)).sort()
  assert.deepEqual(afterVolumes, volumes)
  pass('AI re-enabled: same receipt, quota, database and independent journal volumes')
  report.status = 'PASS'
} catch (error) {
  report.status = 'FAIL'; report.failure = { name: error.name, message: error.message.slice(0, 120) }
  throw error
} finally {
  if (sid) await labControl({ action: 'expire', session_id: sid }).catch(() => {})
  await api.dispose()
  await writeFile(new URL('operations.json', dir), JSON.stringify(report, null, 2) + '\n')
}
