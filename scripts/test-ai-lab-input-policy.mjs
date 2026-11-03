import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { policyVersion, runtimeInputs, runtimePath, verifyRuntimeInputs } from './ai-lab-input-policy.mjs'

assert.equal(runtimePath('Dockerfile'), true)
assert.equal(runtimePath('backend/new-module.py'), true)
assert.equal(runtimePath('docs/report.md'), false)
assert.throws(() => runtimePath('unreviewed/dependency.js'), /Unclassified/)
const dir = await mkdtemp(path.join(tmpdir(), 'ai-input-policy-'))
execFileSync('git', ['init', '-q', dir])
await mkdir(path.join(dir, 'src'))
await writeFile(path.join(dir, 'src/main.ts'), 'export const value = 1\n')
await writeFile(path.join(dir, 'Dockerfile'), 'FROM scratch\n')
const before = runtimeInputs(dir)
const manifest = { schema: policyVersion, inputs: before }
verifyRuntimeInputs(manifest, dir)
await writeFile(path.join(dir, 'src/previously-unlisted.ts'), 'export const hidden = true\n')
assert.throws(() => verifyRuntimeInputs(manifest, dir), /Unreviewed runtime dependency/)
await writeFile(path.join(dir, 'Dockerfile'), 'FROM other\n')
assert.notEqual(runtimeInputs(dir).Dockerfile, before.Dockerfile)
assert.throws(() => verifyRuntimeInputs(manifest, dir), /Unreviewed runtime dependency/)
await mkdir(path.join(dir, 'unreviewed'))
await writeFile(path.join(dir, 'unreviewed/dependency.js'), 'arbitrary runtime\n')
assert.throws(() => runtimeInputs(dir), /Unclassified/)
console.log('PASS: root build input, added dependency, changed input, unknown tree rejected')
