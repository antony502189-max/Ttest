// Tie later docs/evidence-only heads to the exact locally exercised runtime.
// CI verifies source equality; it does not claim to rerun the local Docker stack.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'

const root = new URL('../docs/reports/pr404-remediation-20261103-evidence/', import.meta.url)
const proof = JSON.parse(await readFile(new URL('provenance.json', root), 'utf8'))
assert.match(proof.runtimeSource, /^[0-9a-f]{40}$/)
const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim()
const head = git('rev-parse', 'HEAD')
for (const [path, expected] of Object.entries(proof.runtimeProjection)) {
  assert.equal(git('rev-parse', `HEAD:${path}`), expected, 'Runtime code changed after validation: ' + path)
  assert.equal(git('rev-parse', `${proof.runtimeSource}:${path}`), expected)
}
const hashes = JSON.parse(await readFile(new URL('SHA256.json', root), 'utf8'))
for (const row of hashes) {
  assert.ok(!row.file.includes('/') && !row.file.includes('\\'))
  assert.equal(createHash('sha256').update(await readFile(new URL(row.file, root))).digest('hex'), row.sha256)
}
const result = { ciCheckoutSource: head, validatedRuntimeSource: proof.runtimeSource,
  runtimeProjectionMatches: true, artifactHashesMatch: true, backendImage: proof.backend.image,
  frontendImage: proof.frontend.image, localStackReexecutedInCI: false }
if (process.argv[2]) await writeFile(process.argv[2], JSON.stringify(result, null, 2) + '\n', { flag: 'wx' })
console.log(JSON.stringify(result))
