import { expect, test } from '@playwright/test'

for (const unavailable of [false, true]) test(`private demo ${unavailable ? 'unavailable' : 'exhausted'} blocks new calls and isolates browser CDN`, async ({ page }) => {
  const external: string[] = [], paid: string[] = []
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.hostname !== '127.0.0.1') { external.push(url.hostname); return route.abort() }
    if (url.pathname === '/api/v1/private-demo/status') return unavailable ? route.abort() : route.fulfill({ json: {
      attempts: 3, maximum: 3, exhausted: true, halted: false, next_step: 3,
    } })
    if (url.pathname === '/api/v1/ai-search/capabilities') return route.fulfill({ json: { text: true, map: true, voice: false, saved_searches: false } })
    if (url.pathname.endsWith('/messages')) { paid.push(url.pathname); return route.abort() }
    if (url.pathname.startsWith('/api/')) return route.fulfill({ json: {} })
    return route.continue()
  })
  await page.goto('/#/')
  await page.getByRole('button', { name: 'Escribir mi búsqueda', exact: true }).click()
  await expect(page.locator('[data-private-demo-status]')).toContainText(unavailable ? 'Демостенд недоступен' : 'Демо-лимит исчерпан')
  await page.getByLabel('Modo para esta búsqueda', { exact: true }).selectOption('long')
  await page.getByLabel('Cuéntanos qué necesitas', { exact: true }).fill('до 600 евро в месяц')
  await expect(page.getByRole('button', { name: 'Buscar habitaciones', exact: true })).toBeDisabled()
  // Exercise the exact nginx policy in Chromium: a third-party image/connect
  // must be rejected before even our network interception sees a request.
  await page.evaluate(async () => {
    await fetch('https://cdn.private-demo-csp.invalid/probe').catch(() => undefined)
    await new Promise<void>(resolve => {
      const image = new Image()
      image.onload = image.onerror = () => resolve()
      image.src = 'https://cdn.private-demo-csp.invalid/photo.jpg'
    })
  })
  expect(paid).toEqual([])
  expect(external).toEqual([])
})
