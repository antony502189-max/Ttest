import { expect, test } from '@playwright/test'

for (const width of [390, 1440]) for (const state of ['pending', 'approved', 'unavailable', 'malformed']) {
  test(`site pilot ${width}px ${state} preserves protected-path UI boundary`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => localStorage.setItem('112233:favorites:v2', 'ordinary-site-storage-sentinel'))
    const paid: string[] = [], external: string[] = [], apiPaths: string[] = []
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      if (url.hostname !== '127.0.0.1') { external.push(url.hostname); return route.abort() }
      if (url.pathname.startsWith('/api/')) throw new Error('Pilot escaped its API path')
      if (url.pathname.startsWith('/ai-pilot/api/')) {
        apiPaths.push(url.pathname)
        if (url.pathname.endsWith('/private-demo/status')) return state === 'unavailable' ? route.abort() : route.fulfill({ json: {
          attempts: state === 'malformed' ? '0' : 0, maximum: 50, exhausted: false, halted: state !== 'approved', approved: state === 'approved',
        } })
        if (url.pathname.endsWith('/capabilities')) return route.fulfill({ json: { text: true, map: true, voice: false, saved_searches: false } })
        if (url.pathname.endsWith('/quota')) return route.fulfill({ json: { remaining: 3 } })
        if (url.pathname.endsWith('/query')) { paid.push(url.pathname); return route.abort() }
        return route.fulfill({ json: {} })
      }
      return route.continue()
    })
    await page.goto('./#/')
    await expect(page.getByRole('heading', { name: 'Поиск жилья с AI', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Escribir mi búsqueda', exact: true }).click()
    await expect(page.locator('[data-private-demo-status]')).toContainText(state === 'approved' ? '0/50'
      : state === 'pending' ? 'Страница подготовлена' : 'временно недоступна')
    await expect(page.getByLabel('Modo para esta búsqueda', { exact: true })).toHaveValue('long')
    await page.getByLabel('Cuéntanos qué necesitas', { exact: true }).fill('до 600 евро в месяц')
    const submit = page.getByRole('button', { name: 'Buscar habitaciones', exact: true })
    if (state === 'approved') await expect(submit).toBeEnabled()
    else await expect(submit).toBeDisabled()
    await page.evaluate(() => fetch('https://pilot-csp.invalid/').catch(() => undefined))
    expect(paid).toEqual([])
    expect(external).toEqual([])
    expect(apiPaths).toContain('/ai-pilot/api/v1/private-demo/status')
    expect(await page.evaluate(() => localStorage.getItem('112233:favorites:v2'))).toBe('ordinary-site-storage-sentinel')
  })
}
