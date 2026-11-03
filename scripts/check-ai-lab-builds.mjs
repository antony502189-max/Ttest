// Real config/build regression matrix; no backend/provider, unique outputs.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { build, resolveConfig } from 'vite'

const out = path.resolve(process.argv[2] || 'output/ai-lab-build-matrix-' + crypto.randomUUID())
await mkdir(out, { recursive: false })
const rows = []
process.env.VITE_AI_LAB_SOURCE_SHA = 'a'.repeat(40)
process.env.VITE_ENABLE_MOCK_MODE = '0'
for (const [name, mode, value, expected] of [
  ['production-inherited-live', 'production', 'closed-live-synthetic', ''],
  ['fixture', 'ai-synthetic-lab', 'decision-transport-fixture', 'decision-transport-fixture'],
  ['live-labelled-only', 'ai-synthetic-lab', 'closed-live-synthetic', 'closed-live-synthetic'],
]) {
  process.env.VITE_AI_CLOSED_LAB = value
  const config = await resolveConfig({ mode }, 'build')
  assert.equal(JSON.parse(config.define['import.meta.env.VITE_AI_CLOSED_LAB']), expected)
  const dir = path.join(out, name)
  await build({ mode, logLevel: 'error', build: { outDir: dir, emptyOutDir: false } })
  const html = await readFile(path.join(dir, 'index.html'), 'utf8')
  assert.equal(html.includes('data-i18n-exempt'), Boolean(expected))
  assert.equal(html.includes('Настоящая модель, синтетический каталог'), expected === 'closed-live-synthetic')
  rows.push({ name, passed: true, compiledMode: expected })
}
for (const [value, source] of [['unknown-mode', 'a'.repeat(40)], ['closed-live-synthetic', 'invalid-source']]) {
  process.env.VITE_AI_CLOSED_LAB = value
  process.env.VITE_AI_LAB_SOURCE_SHA = source
  await assert.rejects(resolveConfig({ mode: 'ai-synthetic-lab' }, 'build'), /Explicit valid lab mode/)
  rows.push({ name: value + '/' + source, passed: true, rejected: true })
}
await writeFile(path.join(out, 'result.json'), JSON.stringify({ providerCalls: 0, cases: rows }, null, 2) + '\n', { flag: 'wx' })
console.log(JSON.stringify({ buildMatrix: 'PASS', cases: rows.length, output: out }))
