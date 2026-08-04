import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const dist = path.resolve('dist')
const forbidden = [
  'GoogleDemo112233!',
  'demo112233',
  'admin112233',
]
const inspectedExtensions = new Set(['.html', '.js', '.css', '.json'])

async function filesUnder(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const nested = await Promise.all(entries.map(async (entry) => {
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? filesUnder(target) : [target]
  }))
  return nested.flat()
}

const files = (await filesUnder(dist)).filter((file) => inspectedExtensions.has(path.extname(file)))
if (!files.length) throw new Error('Production bundle is missing or contains no inspectable files')

const findings = []
for (const file of files) {
  const content = await readFile(file, 'utf8')
  for (const value of forbidden) {
    if (content.includes(value)) findings.push({ file: path.relative(dist, file), value })
  }
}

if (findings.length) {
  console.error(JSON.stringify({ productionBundleCredentialFindings: findings }, null, 2))
  throw new Error('Production bundle contains mock credentials')
}
console.log('production-bundle-security: ok')
