import { expect, test } from '@playwright/test'

for (const fault of ['live-backend', 'stale-source', 'unavailable', 'paired']) {
  test(`lab frontend refuses mismatched backend before sessions or query: ${fault}`, async ({ page }) => {
    const writes: string[] = []
    let attestations = 0
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (url.hostname !== '127.0.0.1') return route.abort()
      if (url.pathname === '/api/v1/ai-search/lab-runtime') {
        attestations++
        return route.fulfill({ status: fault === 'unavailable' ? 503 : 200, json: {
          schema: 'ai-lab-runtime.v1', parser: fault === 'live-backend' ? 'closed-live-synthetic' : 'decision-transport-fixture',
          source: (fault === 'stale-source' ? 'b' : 'a').repeat(40),
          instance: '00000000-0000-4000-8000-000000000001', provider_transport: fault === 'live-backend' ? 'https' : 'mock',
        } })
      }
      if (url.pathname.startsWith('/api/v1/ai-search/') && request.method() === 'POST') writes.push(url.pathname)
      if (url.pathname === '/api/v1/ai-search/capabilities') return route.fulfill({ json: { text: true, map: true, voice: false, saved_searches: false } })
      if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 404, json: {} })
      return route.continue()
    })
    await page.addInitScript(() => {
      localStorage.setItem('112233:language:v1', 'es')
      localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
    })
    await page.goto('/#/', { waitUntil: 'networkidle' })
    expect(attestations).toBeGreaterThan(0)
    await expect(page.getByRole('button', { name: 'Escribir mi búsqueda' })).toHaveCount(fault === 'paired' ? 1 : 0)
    expect(writes).toEqual([])
    await expect(page.getByRole('button', { name: 'Ver habitaciones', exact: true })).toBeVisible()
  })
}

test('backend changes after dialog opens: re-attest before identity and session POST', async ({ page }) => {
  let mode = 'decision-transport-fixture'
  let refused = 0
  const writes: string[] = []
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url())
    if (url.hostname !== '127.0.0.1') return route.abort()
    if (url.pathname.endsWith('/ai-search/lab-runtime')) {
      if (mode === 'closed-live-synthetic') refused++
      return route.fulfill({ json: {
      schema: 'ai-lab-runtime.v1', parser: mode, source: 'a'.repeat(40),
      instance: '00000000-0000-4000-8000-000000000001', provider_transport: 'mock',
      } })
    }
    if (url.pathname.startsWith('/api/v1/ai-search/') && request.method() === 'POST') writes.push(url.pathname)
    if (url.pathname.endsWith('/ai-search/capabilities')) return route.fulfill({ json: { text: true, map: true } })
    if (url.pathname.endsWith('/ai-search/quota')) return route.fulfill({ json: { remaining: 3 } })
    if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 404, json: {} })
    return route.continue()
  })
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
  })
  await page.goto('/#/', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Escribir mi búsqueda' }).click()
  await page.locator('#ai-rental-mode').selectOption('none')
  await page.locator('#ai-search-text').fill('Обязательно с балконом.')
  mode = 'closed-live-synthetic'
  await page.locator('.ai-search-dialog > .home-ai-search__action').click()
  await expect.poll(() => refused).toBeGreaterThan(0)
  expect(writes).toEqual([])
})

for (const fault of ['attestation', 'request-race', 'disconnect', 'invalid-json', 'http-500', 'aborted', 'timeout', 'restart']) {
  test(`release mismatch must preserve uncertain operation locator: ${fault}`, async ({ page }) => {
    const writes: string[] = []
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.hostname !== '127.0.0.1') return route.abort()
      if (url.pathname.endsWith('/ai-search/lab-runtime')) {
        if (fault === 'disconnect') return route.abort('connectionrefused')
        if (fault === 'aborted') return route.abort('aborted')
        if (fault === 'invalid-json') return route.fulfill({ status: 200, contentType: 'application/json', body: '{invalid' })
        if (fault === 'http-500') return route.fulfill({ status: 500, json: { detail: 'unavailable' } })
        if (fault === 'timeout') { await new Promise(resolve => setTimeout(resolve, 16000)); return route.abort() }
        return route.fulfill({ json: {
        schema: 'ai-lab-runtime.v1', parser: 'decision-transport-fixture',
        source: (fault === 'attestation' ? 'b' : 'a').repeat(40),
        instance: fault === 'restart' ? '00000000-0000-4000-8000-000000000099' : '00000000-0000-4000-8000-000000000001', provider_transport: 'mock',
      } })
      }
      if (url.pathname.includes('/ai-search/operations/')) return route.fulfill({
        status: 409, json: { detail: 'LAB_RUNTIME_MISMATCH' },
      })
      if (url.pathname.startsWith('/api/v1/ai-search/') && request.method() === 'POST') writes.push(url.pathname)
      if (url.pathname.endsWith('/ai-search/capabilities')) return route.fulfill({ json: { text: false, map: false } })
      if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 404, json: {} })
      return route.continue()
    })
    await page.addInitScript(() => {
      localStorage.setItem('112233:language:v1', 'es')
      localStorage.setItem('112233:mobile-onboarding:v1', 'done:refreshable')
      sessionStorage.setItem('112233:ai-continuation:v1:guest', JSON.stringify({
        sessionId: '00000000-0000-4000-8000-000000000002', operation: {
          key: '00000000-0000-4000-8000-000000000003', expectedVersion: 0, createdAt: Date.now(),
        },
      }))
    })
    await page.goto('/#/', { waitUntil: 'networkidle' })
    const saved = await page.evaluate(() => sessionStorage.getItem('112233:ai-continuation:v1:guest'))
    expect(saved).toContain('00000000-0000-4000-8000-000000000003')
    expect(writes).toEqual([])
  })
}
