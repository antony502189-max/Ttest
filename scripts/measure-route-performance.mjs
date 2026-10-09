import { chromium } from '@playwright/test'

const args = new Map()
for (let index = 2; index < process.argv.length; index += 1) {
  const [key, value] = process.argv[index].split('=', 2)
  if (key?.startsWith('--')) args.set(key.slice(2), value ?? 'true')
}

const baselineUrl = args.get('baseline')
const candidateUrl = args.get('candidate')
if (!baselineUrl || !candidateUrl) {
  throw new Error('Usage: node scripts/measure-route-performance.mjs --baseline=http://127.0.0.1:4174 --candidate=http://127.0.0.1:4175 [--runs=5] [--profile=desktop|mobile|4g|constrained] [--output=results.json]')
}

const runs = Math.max(1, Number(args.get('runs') ?? 5))
const profile = args.get('profile') ?? 'desktop'
const profiles = {
  desktop: { viewport: { width: 1366, height: 768 }, mobile: false, network: null, cpu: 1 },
  mobile: { viewport: { width: 390, height: 844 }, mobile: true, network: null, cpu: 1 },
  '4g': { viewport: { width: 390, height: 844 }, mobile: true, network: { offline: false, latency: 150, downloadThroughput: 1_600_000, uploadThroughput: 750_000, connectionType: 'cellular4g' }, cpu: 4 },
  constrained: { viewport: { width: 390, height: 844 }, mobile: true, network: { offline: false, latency: 300, downloadThroughput: 400_000, uploadThroughput: 200_000, connectionType: 'cellular3g' }, cpu: 4 },
}
const selectedProfile = profiles[profile]
if (!selectedProfile) throw new Error(`Unknown profile: ${profile}`)

const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}) })
const results = []
const targets = [{ name: 'baseline', url: baselineUrl }, { name: 'candidate', url: candidateUrl }]

try {
  for (let run = 1; run <= runs; run += 1) {
    for (const target of (run % 2 ? targets : targets.toReversed())) {
      const route = `${target.url.replace(/\/$/, '')}/#/`
      async function createMeasurementContext(cacheDisabled) {
        const context = await browser.newContext({ viewport: selectedProfile.viewport, isMobile: selectedProfile.mobile, deviceScaleFactor: 1 })
        const page = await context.newPage()
        const cdp = await context.newCDPSession(page)
        const requestUrls = new Map()
        const cacheHitUrls = new Set()
        await cdp.send('Network.enable')
        await cdp.send('Network.setCacheDisabled', { cacheDisabled })
        if (selectedProfile.network) await cdp.send('Network.emulateNetworkConditions', selectedProfile.network)
        if (selectedProfile.cpu > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: selectedProfile.cpu })
        cdp.on('Network.requestWillBeSent', (event) => requestUrls.set(event.requestId, event.request.url))
        cdp.on('Network.requestServedFromCache', (event) => cacheHitUrls.add(requestUrls.get(event.requestId) ?? 'unknown'))
        cdp.on('Network.responseReceived', (event) => {
          if (event.response.fromDiskCache || event.response.fromServiceWorker || event.response.fromPrefetchCache) {
            cacheHitUrls.add(event.response.url)
          }
        })
        await page.addInitScript(() => {
        localStorage.setItem('112233:mobile-onboarding:v1', 'done')
        const imageFixture = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/%3E'
        const originalSetAttribute = Element.prototype.setAttribute
        Element.prototype.setAttribute = function (name, value) {
          if (this instanceof HTMLImageElement && name.toLowerCase() === 'src' && String(value).includes('images.unsplash.com')) value = imageFixture
          return originalSetAttribute.call(this, name, value)
        }
        const src = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')
        if (src?.get && src.set) Object.defineProperty(HTMLImageElement.prototype, 'src', {
          configurable: src.configurable,
          enumerable: src.enumerable,
          get: src.get,
          set(value) { src.set.call(this, String(value).includes('images.unsplash.com') ? imageFixture : value) },
        })
        const stats = { fcp: null, lcp: null, cls: 0 }
        Object.defineProperty(window, '__perfStats', { value: stats })
        new PerformanceObserver((list) => { const item = list.getEntries().at(-1); if (item) stats.fcp = item.startTime }).observe({ type: 'paint', buffered: true })
        new PerformanceObserver((list) => { const item = list.getEntries().at(-1); if (item) stats.lcp = item.startTime }).observe({ type: 'largest-contentful-paint', buffered: true })
        new PerformanceObserver((list) => { for (const item of list.getEntries()) if (!item.hadRecentInput) stats.cls += item.value }).observe({ type: 'layout-shift', buffered: true })
      })
        return { context, page, cdp, cacheHitUrls }
      }
      const sampleNavigation = async ({ page, cacheHitUrls }, cacheMode) => {
        const started = Date.now()
        if (cacheMode === 'warm-after-cache-prime') await page.reload({ waitUntil: 'networkidle', timeout: 60_000 })
        else await page.goto(route, { waitUntil: 'networkidle', timeout: 60_000 })
        await page.waitForTimeout(800)
        const metrics = await page.evaluate(() => {
        const resources = performance.getEntriesByType('resource')
        const nav = performance.getEntriesByType('navigation')[0]
        const resourceBytes = resources.reduce((total, resource) => total + (resource.transferSize || 0), 0)
        return {
          fcpMs: window.__perfStats.fcp,
          lcpMs: window.__perfStats.lcp,
          cls: window.__perfStats.cls,
          ttfbMs: nav?.responseStart ?? null,
          domContentLoadedMs: nav?.domContentLoadedEventEnd ?? null,
          loadMs: nav?.loadEventEnd ?? null,
          requestCount: resources.length,
          transferredBytes: resourceBytes,
          cacheTransferBytes: resources.filter((resource) => resource.transferSize === 0 && resource.decodedBodySize > 0).reduce((total, resource) => total + resource.decodedBodySize, 0),
          jsBytes: resources.filter((resource) => /\.js(?:\?|$)/.test(resource.name)).reduce((total, resource) => total + (resource.transferSize || 0), 0),
          cssBytes: resources.filter((resource) => /\.css(?:\?|$)/.test(resource.name)).reduce((total, resource) => total + (resource.transferSize || 0), 0),
        }
      })
        return { target: target.name, profile, run, cacheMode, wallMs: Date.now() - started, cacheHitCount: cacheHitUrls.size, cachedAssetCount: [...cacheHitUrls].filter((url) => url.includes('/assets/')).length, ...metrics }
      }

      const cold = await createMeasurementContext(true)
      results.push(await sampleNavigation(cold, 'cold-cache-disabled'))
      await cold.context.close()

      const warm = await createMeasurementContext(false)
      await warm.page.goto(route, { waitUntil: 'networkidle', timeout: 60_000 })
      await warm.page.waitForTimeout(800)
      await warm.page.evaluate(() => performance.clearResourceTimings())
      warm.cacheHitUrls.clear()
      results.push(await sampleNavigation(warm, 'warm-after-cache-prime'))
      await warm.context.close()
    }
  }
} finally {
  await browser.close()
}

function summarize(targetName, cacheMode, key) {
  const values = results.filter((row) => row.target === targetName && row.cacheMode === cacheMode).map((row) => row[key]).filter((value) => Number.isFinite(value)).sort((a, b) => a - b)
  if (!values.length) return { n: 0, median: null, min: null, max: null }
  return { n: values.length, median: values[Math.floor(values.length / 2)], min: values[0], max: values.at(-1) }
}
const summary = Object.fromEntries(targets.map(({ name }) => [name, Object.fromEntries(['cold-cache-disabled', 'warm-after-cache-prime'].map((cacheMode) => [cacheMode, Object.fromEntries(['fcpMs', 'lcpMs', 'cls', 'ttfbMs', 'requestCount', 'cacheHitCount', 'cachedAssetCount', 'transferredBytes', 'cacheTransferBytes', 'jsBytes', 'cssBytes'].map((metric) => [metric, summarize(name, cacheMode, metric)]))]))]))
const output = { schemaVersion: 1, generatedAt: new Date().toISOString(), measurementKind: 'local synthetic browser measurement using a local static server with immutable hashed assets', warmMethod: 'A separate cache-enabled browser context first visits the target to prime HTTP cache; the measured navigation then reloads in the same context.', profile, runsPerTarget: runs, conditions: selectedProfile, targets: { baseline: baselineUrl, candidate: candidateUrl }, results, summary }
const serialized = `${JSON.stringify(output, null, 2)}\n`
if (args.has('output')) await import('node:fs/promises').then((fs) => fs.writeFile(args.get('output'), serialized))
process.stdout.write(serialized)
