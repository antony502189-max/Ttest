import assert from 'node:assert/strict'
import { resolveConfig } from 'vite'
const names = ['VITE_BASE_PATH', 'VITE_API_BASE_URL', 'VITE_ENABLE_MOCK_MODE']
const saved = Object.fromEntries(names.map(name => [name, process.env[name]]))
try {
  for (const name of names) delete process.env[name]
  const clean = await resolveConfig({ mode: 'ai-site-pilot' }, 'build')
  assert.equal(clean.base, '/ai-pilot/')
  assert.equal(JSON.parse(clean.define['import.meta.env.VITE_API_BASE_URL']), '/ai-pilot/api/v1')
  assert.equal(JSON.parse(clean.define['import.meta.env.VITE_ENABLE_MOCK_MODE']), '0')
  for (const [name, wrong] of [['VITE_BASE_PATH', '/'], ['VITE_API_BASE_URL', '/api/v1'], ['VITE_API_BASE_URL', 'https://example.com/api'], ['VITE_ENABLE_MOCK_MODE', '1']]) {
    process.env[name] = wrong
    await assert.rejects(resolveConfig({ mode: 'ai-site-pilot' }, 'build'), /PILOT_BUILD_CONFIGURATION_REJECTED/)
    delete process.env[name]
  }
  console.log('PASS: clean pilot defaults and four contradictory build inputs rejected')
} finally { for (const name of names) { if (saved[name] === undefined) delete process.env[name]; else process.env[name] = saved[name] } }
