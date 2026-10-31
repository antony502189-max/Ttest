// Local-only acceptance controls. No remote HTTP administrator endpoint.
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'
const exec = promisify(execFile)
export async function labControl(payload) {
  const target = 'ttest-ai-text-lab-backend'
  const inspected = await exec('docker', ['inspect', '--format', '{{json .Config.Labels}}', target], { timeout: 10000 })
  if (JSON.parse(inspected.stdout)['es.ttest.purpose'] !== 'ai-text-synthetic-lab-v1') throw Error('Foreign container')
  const result = await exec('docker', ['exec', target, 'python', '-m', 'lab.acceptance', JSON.stringify(payload)], { timeout: 30000 })
  return JSON.parse(result.stdout)
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [action, first, second, third] = process.argv.slice(2)
  let payload
  if (action === 'seed') payload = { action }
  else if (action === 'change') payload = { action, name: first, kind: second }
  else if (['inspect', 'arm', 'expire'].includes(action)) payload = {
    action, session_id: first, ...(second === undefined ? {} : { version: Number(second) }), ...(third ? { fault: third } : {}),
  }
  else throw Error('Use: seed | change NAME source/price/moderation/hidden/missing/proof/restore | inspect UUID VERSION | arm UUID VERSION delay/failure/cancel | expire UUID')
  console.log(JSON.stringify(await labControl(payload), null, 2))
}
