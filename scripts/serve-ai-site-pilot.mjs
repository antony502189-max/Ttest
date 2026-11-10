// Offline build/HTTP contracts only. No provider credentials or backend.
import { build, preview } from 'vite'
import { readFile } from 'node:fs/promises'
const nginx = await readFile('deploy/ai-site-pilot/nginx.conf', 'utf8')
const csp = nginx.match(/add_header Content-Security-Policy "([^"]+)" always;/)?.[1]
const microphonePolicy = nginx.match(/add_header Permissions-Policy "([^"]+)" always;/)?.[1]
if (!csp) throw new Error('Pilot CSP required')
if (microphonePolicy !== 'camera=(), microphone=(self)') throw new Error('Pilot microphone permission policy required')
process.env.VITE_ENABLE_MOCK_MODE = '0'
process.env.VITE_API_BASE_URL = '/ai-pilot/api/v1'
process.env.VITE_BASE_PATH = '/ai-pilot/'
const outDir = 'output/site-pilot-contract-dist'
await build({ mode: 'ai-site-pilot', build: { outDir, emptyOutDir: true, reportCompressedSize: false } })
await preview({ preview: { host: '127.0.0.1', port: 4178, strictPort: true, headers: {
  'Content-Security-Policy': csp,
  'Permissions-Policy': microphonePolicy,
} }, build: { outDir } })
