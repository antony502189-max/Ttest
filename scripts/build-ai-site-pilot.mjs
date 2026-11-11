// One production build command. No deployment/provider IO.
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { isIP } from 'node:net'
import { readFile, readdir, writeFile } from 'node:fs/promises'
import { build } from 'vite'
const peer = process.argv[2]
if (isIP(peer ?? '') !== 4 || ['0.0.0.0', '127.0.0.1'].includes(peer)) throw new Error('Explicit verified Traefik IPv4 peer required')
const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim()
if (git('status', '--porcelain')) throw new Error('Clean committed source required for pilot release build')
const source = git('rev-parse', 'HEAD')
await build({ mode: 'ai-site-pilot', build: { outDir: 'output/site-pilot-dist', emptyOutDir: true } })
const publicAccess = process.argv[3] === '--public'
if (process.argv[3] && !publicAccess) throw new Error('Unknown access mode')
const template = await readFile(publicAccess ? 'deploy/ai-site-pilot/nginx-public.conf' : 'deploy/ai-site-pilot/nginx.conf', 'utf8')
await writeFile('output/site-pilot-nginx.conf', template.replaceAll('__TRAEFIK_IP__', peer))
const files = {}
for (const file of await readdir('output/site-pilot-dist', { recursive: true })) {
  if (file.endsWith('.js') || file === 'index.html') {
    const value = await readFile('output/site-pilot-dist/' + file)
    const text = value.toString()
    if (/['"]\/api\/v1(?:[/'"])/.test(text) || /['"]\/assets\//.test(text)) throw new Error('Pilot escaped protected API/assets prefix: ' + file)
    files[file.replaceAll('\\', '/')] = createHash('sha256').update(value).digest('hex')
  }
}
await writeFile('output/site-pilot-dist/build-manifest.json', JSON.stringify({ source, access: publicAccess ? 'public' : 'private', mode: 'ai-site-pilot', base: '/ai-pilot/', api: '/ai-pilot/api/v1', mock: false, traefikPeer: peer, files }, null, 2))
await writeFile('output/site-pilot-build.env', `PILOT_SOURCE_SHA=${source}\n`)
