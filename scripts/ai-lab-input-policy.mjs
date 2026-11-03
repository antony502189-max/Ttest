// Reviewed dependency boundary v1. Entire trees are included, not a hand-picked
// projection. A new top-level directory must be classified in code review.
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'

export const policyVersion = 'ai-lab-runtime-inputs.v1'
const runtimeTrees = new Set(['backend', 'src', 'scripts', 'deploy', 'public', '.github'])
const nonRuntimeTrees = new Set(['docs', 'reports', 'artifacts', 'tests', 'qa'])

export function runtimePath(file) {
  assert.ok(!file.startsWith('/') && !file.split('/').includes('..'), 'Invalid source path')
  if (!file.includes('/')) return !file.endsWith('.md') && !file.endsWith('.log')
  const tree = file.split('/')[0]
  assert.ok(runtimeTrees.has(tree) || nonRuntimeTrees.has(tree), 'Unclassified dependency tree: ' + tree)
  return runtimeTrees.has(tree)
}

export function runtimeInputs(cwd = process.cwd()) {
  const git = (...args) => execFileSync('git', args, { cwd, encoding: 'utf8' }).trim()
  const files = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').split('\0').filter(Boolean)
  const included = [...new Set(files)].filter(runtimePath).sort()
  for (const file of included) assert.ok(!/["\r\n]/.test(file), 'Unsupported source filename requires review')
  if (!included.length) return {}
  const blobs = execFileSync('git', ['hash-object', '--stdin-paths'],
    { cwd, encoding: 'utf8', input: included.join('\n') + '\n' }).trim().split('\n')
  assert.equal(blobs.length, included.length)
  return Object.fromEntries(included.map((file, i) => [file, blobs[i]]))
}

export function committedRuntimeInputs(ref, cwd = process.cwd()) {
  assert.match(ref, /^[0-9a-f]{40}$/)
  const rows = execFileSync('git', ['ls-tree', '-r', '-z', '--format=%(objectname) %(path)', ref],
    { cwd, encoding: 'utf8' }).split('\0').filter(Boolean)
  return Object.fromEntries(rows.map(row => [row.slice(41), row.slice(0, 40)])
    .filter(([file]) => runtimePath(file)).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))
}

export function verifyRuntimeInputs(manifest, cwd = process.cwd()) {
  assert.equal(manifest.schema, policyVersion)
  const actual = runtimeInputs(cwd)
  assert.deepEqual(actual, manifest.inputs, 'Unreviewed runtime dependency changed/added/removed')
  return actual
}
