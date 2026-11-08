// Offline browser regression server; APIs are intercepted by the test.
import { build, preview } from 'vite'
import { readFile } from 'node:fs/promises'
const nginx = await readFile('deploy/ai-text-demo/nginx.conf', 'utf8')
const csp = nginx.match(/add_header Content-Security-Policy "([^"]+)" always;/)?.[1]
if (!csp) throw new Error('Private nginx CSP is required')
process.env.VITE_ENABLE_MOCK_MODE = '0'
process.env.VITE_API_BASE_URL = '/api/v1'
const outDir = 'output/private-demo-contract-dist'
await build({ mode: 'ai-private-demo', build: { outDir, emptyOutDir: true, reportCompressedSize: false } })
await preview({ preview: { host: '127.0.0.1', port: 4177, strictPort: true, headers: {
  'Content-Security-Policy': csp,
} }, build: { outDir } })
