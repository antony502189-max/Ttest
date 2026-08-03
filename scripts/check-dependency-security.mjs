import { spawnSync } from 'node:child_process'

const npm = process.platform === 'win32' ? process.execPath : 'npm'
const npmArgs = process.platform === 'win32'
  ? [process.env.npm_execpath, 'audit', '--omit=dev', '--json']
  : ['audit', '--omit=dev', '--json']
const auditProcess = spawnSync(npm, npmArgs, { encoding: 'utf8' })
if (auditProcess.error) throw auditProcess.error

let audit
try {
  audit = JSON.parse(auditProcess.stdout)
} catch (error) {
  const stderr = auditProcess.stderr.trim()
  throw new Error(`npm audit returned invalid JSON${stderr ? `: ${stderr}` : ''}`, { cause: error })
}

const unexpected = []
for (const [name, vulnerability] of Object.entries(audit.vulnerabilities ?? {})) {
  if (!['high', 'critical'].includes(vulnerability.severity)) continue
  unexpected.push({
    name,
    severity: vulnerability.severity,
    range: vulnerability.range,
    nodes: vulnerability.nodes,
    via: (vulnerability.via ?? []).map((entry) => (
      typeof entry === 'string'
        ? entry
        : {
            name: entry.name,
            title: entry.title,
            url: entry.url,
            range: entry.range,
          }
    )),
    effects: vulnerability.effects,
    fixAvailable: vulnerability.fixAvailable,
  })
}

if (unexpected.length) {
  console.error(JSON.stringify({ dependencyAuditFindings: unexpected }, null, 2))
  throw new Error(
    `Unexpected high or critical dependency audit findings: ${unexpected.map(({ name }) => name).join(', ')}`,
  )
}
console.log('dependency-security-policy: ok')
