import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const options = new Map(process.argv.slice(2).map((arg) => {
  const [key, ...rest] = arg.replace(/^--/, '').split('=')
  return [key, rest.join('=')]
}))
const root = path.resolve(options.get('root') ?? '')
const port = Number(options.get('port') ?? 4174)
if (!options.get('root') || !Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('Usage: node scripts/serve-build-for-measurement.mjs --root=ABSOLUTE_BUILD_DIR --port=4174')
}

const mime = new Map([
  ['.css', 'text/css; charset=utf-8'], ['.geojson', 'application/geo+json'], ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'], ['.js', 'text/javascript; charset=utf-8'], ['.json', 'application/json'],
  ['.jpg', 'image/jpeg'], ['.jpeg', 'image/jpeg'], ['.png', 'image/png'], ['.svg', 'image/svg+xml'],
  ['.webp', 'image/webp'], ['.woff', 'font/woff'], ['.woff2', 'font/woff2'],
])

const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://localhost').pathname)
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '')
    let file = path.resolve(root, relative)
    if (!file.startsWith(`${root}${path.sep}`) && file !== path.join(root, 'index.html')) {
      response.writeHead(400).end('bad path')
      return
    }
    try {
      if (!(await stat(file)).isFile()) file = path.join(root, 'index.html')
    } catch {
      file = path.join(root, 'index.html')
    }
    const details = await stat(file)
    const etag = `W/"${details.size.toString(16)}-${Math.trunc(details.mtimeMs).toString(16)}"`
    const hashedAsset = /-[A-Za-z0-9_-]{8,}\.(?:css|geojson|ico|jpe?g|js|png|svg|webp|woff2?)$/i.test(path.basename(file))
    response.setHeader('Cache-Control', hashedAsset ? 'public, max-age=31536000, immutable' : 'no-cache')
    response.setHeader('ETag', etag)
    response.setHeader('Vary', 'Accept-Encoding')
    response.setHeader('X-Content-Type-Options', 'nosniff')
    response.setHeader('Content-Type', mime.get(path.extname(file).toLowerCase()) ?? 'application/octet-stream')
    if (request.headers['if-none-match'] === etag) {
      response.writeHead(304).end()
      return
    }
    response.writeHead(200, { 'Content-Length': details.size })
    createReadStream(file).pipe(response)
  } catch {
    response.writeHead(500).end('measurement server error')
  }
})

server.listen(port, '127.0.0.1', () => process.stdout.write(`Serving ${root} at http://127.0.0.1:${port}\n`))
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)))
