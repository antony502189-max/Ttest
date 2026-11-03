// Independent read-only inspection of effective Docker state. Does not start,
// sign, authorize or change anything. Never serializes raw secret environment.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { writeFile } from 'node:fs/promises'

const [source, backendName, frontendName, output] = process.argv.slice(2)
assert.match(source ?? '', /^[0-9a-f]{40}$/)
assert.ok(backendName && frontendName && output, 'source backend-container frontend-container output required')
const inspect = (name) => JSON.parse(execFileSync('docker', ['inspect', name], { encoding: 'utf8', timeout: 10000 }))[0]
const records = []
for (const [role, name] of [['backend', backendName], ['frontend', frontendName]]) {
  const c = inspect(name)
  assert.ok(c.State.Running)
  assert.match(c.Image, /^sha256:[0-9a-f]{64}$/)
  assert.equal(c.Config.Labels['org.opencontainers.image.revision'], source)
  const env = Object.fromEntries(c.Config.Env.map(v => { const i = v.indexOf('='); return [v.slice(0, i), v.slice(i + 1)] }))
  assert.ok(!Object.keys(env).some(k => /DEEPSEEK.*KEY|CLOSED_UI_AUTHORITY/.test(k) && /KEY/.test(k)), 'Secrets must be mounted, not exported')
  if (role === 'backend') {
    assert.equal(Object.values(c.NetworkSettings.Ports ?? {}).some(Boolean), false, 'Backend ports must not be published')
    assert.equal(env.AI_LAB_SOURCE_SHA, source)
    assert.ok(c.Config.User && c.Config.User !== 'root' && c.Config.User !== '0')
  } else {
    assert.ok(Object.values(c.NetworkSettings.Ports ?? {}).flat().filter(Boolean).every(p => p.HostIp === '127.0.0.1'))
  }
  records.push({ role, image: c.Image, imageRepoDigests: inspect(c.Image).RepoDigests ?? [],
    environmentNames: Object.keys(env).sort(), environment: Object.fromEntries(
      ['APP_ENV', 'AI_LAB_PARSER', 'AI_LAB_SOURCE_SHA', 'AI_SYNTHETIC_LAB'].filter(k => k in env).map(k => [k, env[k]])),
    user: c.Config.User, networks: Object.keys(c.NetworkSettings.Networks).sort(),
    mounts: c.Mounts.map(m => ({ destination: m.Destination, type: m.Type, readOnly: !m.RW })),
    effectiveConfigSha256: createHash('sha256').update(JSON.stringify({ Config: c.Config, HostConfig: c.HostConfig })).digest('hex') })
}
await writeFile(output, JSON.stringify({ schema: 'ai-lab-container-inspection.v1', inspectedAt: new Date().toISOString(),
  source, records, providerCallsMadeByInspector: 0, provesProviderBillingControls: false, provesStackTestsPassed: false }, null, 2) + '\n', { flag: 'wx' })
