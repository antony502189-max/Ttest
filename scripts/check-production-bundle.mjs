import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const dist = path.resolve('dist')
const forbidden = [
  // Plain-text mock credentials.
  'GoogleDemo112233!',
  'demo112233',
  'admin112233',
  // Demo account identifiers and credential-derived material must also be
  // removed by the production build rather than shipped to browsers.
  'tenant-demo',
  'host-demo',
  'admin-demo',
  'inquilina@112233.es',
  'anfitrion@112233.es',
  'admin@112233.es',
  '9f43cf3b2ee389bd63013060127a8243c50580f829de40f817aeba77b531eed6',
  'aa5ff7ddeca7848ed7eb16270306d14ba2f7b65171ca0e700ec2e2adda115b83',
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
  throw new Error('Production bundle contains mock credentials or demo account material')
}
console.log('production-bundle-security: ok')
