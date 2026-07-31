import { spawnSync } from 'node:child_process'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const npm = process.platform === 'win32' ? process.execPath : 'npm'
const npmArgs = process.platform === 'win32'
  ? [process.env.npm_execpath, 'audit', '--omit=dev', '--json']
  : ['audit', '--omit=dev', '--json']
const auditProcess = spawnSync(npm, npmArgs, { encoding: 'utf8' })
if (auditProcess.error) throw auditProcess.error
const auditOutput = auditProcess.stdout

const audit = JSON.parse(auditOutput)
const allowedRscAdvisory = 'https://github.com/advisories/GHSA-qwww-vcr4-c8h2'
const allowedPackages = new Set(['react-router', 'react-router-dom'])
const unexpected = []

for (const [name, vulnerability] of Object.entries(audit.vulnerabilities ?? {})) {
  if (!['high', 'critical'].includes(vulnerability.severity)) continue
  const advisoryUrls = vulnerability.via
    .filter((item) => typeof item === 'object')
    .map((item) => item.url)
  const isOnlyAllowedRscFinding =
    allowedPackages.has(name) &&
    vulnerability.severity === 'high' &&
    advisoryUrls.every((url) => url === allowedRscAdvisory)
  if (!isOnlyAllowedRscFinding) unexpected.push(name)
}

function readSourceTree(directory) {
  return readdirSync(directory, { withFileTypes: true })
    .flatMap((entry) => {
      const path = join(directory, entry.name)
      return entry.isDirectory() ? readSourceTree(path) : [readFileSync(path, 'utf8')]
    })
    .join('\n')
}

const source = readSourceTree('src')
if (/unstable_RSC|RSCHydratedRouter|RSCStaticRouter|ServerRouter/.test(source)) {
  unexpected.push('unstable React Router RSC API usage')
}
if (unexpected.length) {
  throw new Error(`Unexpected high or critical dependency audit findings: ${unexpected.join(', ')}`)
}
console.log('dependency-security-policy: ok')
