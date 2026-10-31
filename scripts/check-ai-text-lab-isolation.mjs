import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { request } from '@playwright/test'

const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8', timeout: 30_000 }).trim()
const inspect = name => JSON.parse(docker('inspect', name))[0]
const prefix = 'ttest-ai-text-lab-'
const purpose = 'ai-text-synthetic-lab-v1'
const source = JSON.parse(await readFile(new URL('../output/ai-text-lab/source.json', import.meta.url), 'utf8')).source
const evidence = { source, checks: [], resources: [] }
for (const service of ['postgres', 'redis', 'backend', 'frontend']) {
  const container = inspect(prefix + service)
  assert.equal(container.Config.Labels['es.ttest.purpose'], purpose)
  assert.equal(container.Config.Labels['org.opencontainers.image.revision'], source)
  const networks = Object.keys(container.NetworkSettings.Networks).sort()
  assert.deepEqual(networks, service === 'frontend' ? [prefix + 'loopback', prefix + 'network'] : [prefix + 'network'])
  const ports = container.NetworkSettings.Ports
  const published = Object.values(ports || {}).filter(Boolean).flat()
  if (service === 'frontend') assert.deepEqual(published, [{ HostIp: '127.0.0.1', HostPort: '9443' }])
  else assert.deepEqual(published, [])
  evidence.resources.push({ name: container.Name.slice(1), imageId: container.Image, image: container.Config.Image,
    networks, ports, mounts: container.Mounts.map(m => ({ type: m.Type, name: m.Name, destination: m.Destination })) })
}
const network = JSON.parse(docker('network', 'inspect', prefix + 'network'))[0]
assert.equal(network.Internal, true)
assert.equal(network.Labels['es.ttest.purpose'], purpose)
const route = docker('exec', prefix + 'backend', 'cat', '/proc/net/route')
assert.ok(!route.split('\n').some(line => line.split(/\s+/)[1] === '00000000'))
evidence.checks.push('isolated resources; only frontend loopback TLS published; backend has no default route')
const probe = `import asyncio, uuid
from app.services.rate_limit import RedisRateLimiter
from app.services.ai_search_attempts import AIAttemptGate, AIAttemptRejected
from app.schemas.ai_search_quota import QuotaSubject
from lab.ai_text import require_lab, verify_database
from app.db.session import SessionLocal, engine
async def run():
    require_lab()
    await verify_database(SessionLocal)
    first, second = RedisRateLimiter('redis://redis:6379/0'), RedisRateLimiter('redis://redis:6379/0')
    owner = QuotaSubject(kind='guest', id=uuid.uuid4())
    await AIAttemptGate(first, attempts=1, window_seconds=60).check(owner)
    try:
        await AIAttemptGate(second, attempts=1, window_seconds=60).check(owner)
    except AIAttemptRejected as error:
        assert error.code == 'ATTEMPT_LIMIT'
    else:
        raise AssertionError('independent instance bypassed Redis gate')
    await first.close()
    await second.close()
    await engine.dispose()
asyncio.run(run())
print('shared Redis gate + dedicated database marker: PASS')`
evidence.checks.push(docker('exec', prefix + 'backend', 'python', '-c', probe))
const api = await request.newContext({ ignoreHTTPSErrors: true, timeout: 10_000,
  baseURL: 'https://localhost:9443', extraHTTPHeaders: { Origin: 'https://localhost:9443', 'X-AI-Request': '1' } })
try {
  // Explicitly only our labelled Redis. Always restore it, including on failure.
  try {
    docker('stop', '--time', '5', prefix + 'redis')
    const rejected = await api.get('/api/v1/ai-search/quota')
    assert.equal(rejected.status(), 503)
    assert.deepEqual(await rejected.json(), { detail: 'ABUSE_GATE_UNAVAILABLE' })
    assert.deepEqual([...new Set(rejected.headers()['cache-control'].split(',').map(value => value.trim()))], ['no-store'])
    evidence.checks.push('real Redis outage: AI HTTP gate fails closed with 503, no-store')
  } finally { docker('start', prefix + 'redis') }
  let ready = false
  for (let attempt = 0; attempt < 20; attempt++) {
    const response = await api.post('/api/v1/ai-search/identity')
    if (response.ok()) { ready = true; break }
    await new Promise(resolve => setTimeout(resolve, 250))
  }
  assert.ok(ready, 'Redis recovery failed')
  const quota = await api.get('/api/v1/ai-search/quota')
  assert.equal(quota.status(), 200)
  assert.equal((await quota.json()).used, 0)
  evidence.checks.push('real Redis recovery restores AI; no business debit')
  evidence.status = 'PASS'
} finally {
  await api.dispose()
  const dir = new URL('../output/ai-text-lab-smoke/', import.meta.url)
  await mkdir(dir, { recursive: true })
  await writeFile(new URL('isolation.json', dir), JSON.stringify(evidence, null, 2) + '\n')
}
console.log(JSON.stringify({ status: evidence.status, source, checks: evidence.checks }))
