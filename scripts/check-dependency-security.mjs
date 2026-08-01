import { spawnSync } from 'node:child_process'

const npm = process.platform === 'win32' ? process.execPath : 'npm'
const npmArgs = process.platform === 'win32'
  ? [process.env.npm_execpath, 'audit', '--omit=dev', '--json']
  : ['audit', '--omit=dev', '--json']
const auditProcess = spawnSync(npm, npmArgs, { encoding: 'utf8' })
if (auditProcess.error) throw auditProcess.error
const auditOutput = auditProcess.stdout

const audit = JSON.parse(auditOutput)
const unexpected = []

for (const [name, vulnerability] of Object.entries(audit.vulnerabilities ?? {})) {
  if (!['high', 'critical'].includes(vulnerability.severity)) continue
  unexpected.push(name)
}
if (unexpected.length) {
  throw new Error(`Unexpected high or critical dependency audit findings: ${unexpected.join(', ')}`)
}
console.log('dependency-security-policy: ok')
