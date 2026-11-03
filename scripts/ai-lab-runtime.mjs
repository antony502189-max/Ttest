// Backend and Docker attestation. Static frontend JSON is never sufficient.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'

export function pairedHeaders(runtime) {
  return { 'X-AI-Lab-Mode': runtime.parser, 'X-AI-Lab-Source': runtime.source, 'X-AI-Lab-Instance': runtime.instance }
}

export async function attestOfflineBackend(ctx, source, parser = 'decision-transport-fixture') {
  const docker = (...args) => JSON.parse(execFileSync('docker', args, { encoding: 'utf8', timeout: 10000 }))
  const [backend] = docker('inspect', 'ttest-ai-text-lab-backend')
  assert.equal(backend.Config.Labels['es.ttest.purpose'], 'ai-text-synthetic-lab-v1')
  assert.equal(backend.Config.Labels['org.opencontainers.image.revision'], source)
  assert.deepEqual(Object.keys(backend.NetworkSettings.Networks), ['ttest-ai-text-lab-network'])
  const [network] = docker('network', 'inspect', 'ttest-ai-text-lab-network')
  assert.equal(network.Internal, true)
  assert.ok(!backend.Mounts.some(m => /closed-ui-(budget|secrets|admission)/.test(m.Destination)))
  const response = await ctx.request.get('https://localhost:9443/api/v1/ai-search/lab-runtime')
  assert.equal(response.status(), 200)
  const runtime = await response.json()
  assert.equal(runtime.schema, 'ai-lab-runtime.v1')
  assert.equal(runtime.parser, parser)
  assert.equal(runtime.source, source)
  assert.equal(runtime.provider_transport, parser === 'finite' ? 'none' : 'mock')
  assert.match(runtime.instance, /^[0-9a-f-]{36}$/)
  await ctx.setExtraHTTPHeaders(pairedHeaders(runtime))
  return { ...runtime, backendImage: backend.Image, internalNetwork: true, verifiedProviderCalls: 0 }
}
