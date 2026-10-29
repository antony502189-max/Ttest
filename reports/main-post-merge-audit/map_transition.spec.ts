import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })
test('audit: search-area navigation and delayed camera updates retain one route authority', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    const events: unknown[] = []
    let injected = false
    Object.assign(window, { auditRouteEvents: events })
    for (const method of ['pushState', 'replaceState'] as const) {
      const original = history[method].bind(history)
      history[method] = (...args: Parameters<History[typeof method]>) => {
        events.push({ method, url: String(args[2]), stack: new Error().stack })
        const answer = original(...args)
        if (!injected && method === 'pushState' && String(args[2]).includes('poligono=') && !String(args[2]).includes('dibujar=1')) {
          injected = true
          queueMicrotask(() => {
            const map = (window as unknown as { __googleMapsTestLastMap?: { setCenter(point: {lat: number; lng: number}): void } }).__googleMapsTestLastMap
            map?.setCenter({ lat: 28.15, lng: -16.62 })
          })
        }
        return answer
      }
    }
  })
  const polygon = '28.00000,-16.79000;28.00000,-16.50000;28.17000,-16.50000;28.17000,-16.79000'
  await page.goto(`/#/buscar?q=Tenerife&alquiler=long&vista=mapa&dibujar=1&poligono=${encodeURIComponent(polygon)}`)
  const search = page.getByTestId('search-this-area')
  await expect(search).toBeVisible()
  await expect(page).toHaveURL(/mapZoom=/)
  await search.click()
  try {
    await expect(page).not.toHaveURL(/dibujar=1/)
  } finally {
    console.log(JSON.stringify(await page.evaluate(() => ({
      url: location.href,
      events: (window as unknown as { auditRouteEvents: unknown[] }).auditRouteEvents,
    })), null, 2))
  }
})
