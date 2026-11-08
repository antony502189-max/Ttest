// Offline browser regression server; APIs are intercepted by the test.
import { build, preview } from 'vite'
process.env.VITE_ENABLE_MOCK_MODE = '0'
process.env.VITE_API_BASE_URL = '/api/v1'
const outDir = 'output/private-demo-contract-dist'
await build({ mode: 'ai-private-demo', build: { outDir, emptyOutDir: true, reportCompressedSize: false } })
await preview({ preview: { host: '127.0.0.1', port: 4177, strictPort: true, headers: {
  'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; object-src 'none'; base-uri 'self'",
} }, build: { outDir } })
