// Verify historical evidence at ITS source and current inputs independently.
// Changed runtime code cannot inherit historical Docker acceptance.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { committedRuntimeInputs, verifyRuntimeInputs } from './ai-lab-input-policy.mjs'

const root = new URL('../docs/reports/pr404-recovery-final-20261103-evidence/', import.meta.url)
const proof = JSON.parse(await readFile(new URL('provenance.json', root), 'utf8'))
assert.match(proof.runtimeSource, /^[0-9a-f]{40}$/)
const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim()
const head = git('rev-parse', 'HEAD')
for (const [path, expected] of Object.entries(proof.runtimeProjection)) {
  assert.equal(git('rev-parse', `${proof.runtimeSource}:${path}`), expected, 'Historical proof changed: ' + path)
}
const hashes = JSON.parse(await readFile(new URL('SHA256.json', root), 'utf8'))
const seen = new Set()
for (const row of hashes) {
  assert.ok(!row.file.includes('/') && !row.file.includes('\\') && !seen.has(row.file))
  seen.add(row.file)
  assert.equal(createHash('sha256').update(await readFile(new URL(row.file, root))).digest('hex'), row.sha256)
}
assert.deepEqual((await readdir(root)).filter(file => file !== 'SHA256.json').sort(), [...seen].sort(),
  'Unlisted historical artifact added/removed')
const manifest = JSON.parse(await readFile(new URL('../docs/reports/pr404-review-fixes/runtime-inputs.json', import.meta.url), 'utf8'))
const currentInputs = verifyRuntimeInputs(manifest)
const validationRoot = new URL('../docs/reports/pr404-review-fixes/', import.meta.url)
const validation = JSON.parse(await readFile(new URL('validation.json', validationRoot), 'utf8'))
for (const row of validation.artifacts) {
  assert.ok(!row.file.includes('/') && !row.file.includes('\\'))
  assert.equal(createHash('sha256').update(await readFile(new URL(row.file, validationRoot))).digest('hex'), row.sha256,
    'Current validation artifact changed: ' + row.file)
}
const historicalMatches = JSON.stringify(currentInputs) === JSON.stringify(committedRuntimeInputs(proof.runtimeSource))
const result = { ciCheckoutSource: head, historicalValidatedRuntimeSource: proof.runtimeSource,
  currentRuntimeInputsMatch: true, currentRuntimeInputCount: Object.keys(manifest.inputs).length,
  artifactHashesMatch: true, historicalEvidenceAppliesToCurrentRuntime: historicalMatches,
  historicalBackendImage: proof.backend.image, historicalFrontendImage: proof.frontend.image,
  localStackReexecutedInCI: false, currentContainerAcceptance: 'requires independent container attestation and stack run' }
if (process.argv[2]) await writeFile(process.argv[2], JSON.stringify(result, null, 2) + '\n', { flag: 'wx' })
console.log(JSON.stringify(result))
